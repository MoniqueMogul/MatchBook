"""
Document processing pipeline.

Celery task that runs in the shared worker infrastructure
from app.core.celery_app.
"""

from uuid import UUID

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.db_enum import VerificationStatus
from app.verification.document_processing import confidence, extractor
from app.verification.integrations import storage
from app.verification.repositories import documents as documents_repo
from app.verification.services import discrepancy_service


@celery_app.task(name="app.verification.tasks.document_tasks.process_document_task")
def process_document_task(document_id: str) -> None:
    db = SessionLocal()
    try:
        document = documents_repo.get_by_id(db, UUID(document_id))
        if document is None:
            return
        if document.verification_status == VerificationStatus.VERIFIED:
            return

        expected_type = getattr(document.document_type, "value", document.document_type)

        documents_repo.update_status(db, document.id, VerificationStatus.PROCESSING)

        raw_bytes = storage.get_object_bytes(document.bucket_name, document.object_key)
        document_text = _extract_text(raw_bytes, document.mime_type)
        classification_result = _run_classification_sync(
            document_id=str(document.id),
            expected_type=expected_type,
            document_text=document_text,
        )

        cls = classification_result.classification

        if not cls.matches_expected:
            documents_repo.update_status(
                db,
                document.id,
                VerificationStatus.REQUIRES_REVIEW,
                metadata={
                    "expected_type": classification_result.expected_type,
                    "detected_type": cls.detected_type,
                    "confidence": cls.confidence,
                },
            )
            discrepancy_service.flag_for_review(
                db,
                discrepancy_service.document_type_mismatch_discrepancy(
                    entity_type="document",
                    entity_id=document.id,
                    expected_type=classification_result.expected_type,
                    detected_type=cls.detected_type,
                    confidence=cls.confidence,
                ),
            )
            return

        if confidence.is_low_confidence(cls.confidence):
            documents_repo.update_status(
                db,
                document.id,
                VerificationStatus.REQUIRES_REVIEW,
                metadata={
                    "expected_type": classification_result.expected_type,
                    "detected_type": cls.detected_type,
                    "confidence": cls.confidence,
                },
            )
            discrepancy_service.flag_for_review(
                db,
                discrepancy_service.low_confidence_discrepancy(
                    entity_type="document",
                    entity_id=document.id,
                    field_name="document_type_classification",
                    confidence=cls.confidence,
                    threshold=confidence.LOW_CONFIDENCE_THRESHOLD,
                ),
            )
            return

        documents_repo.update_status(
            db,
            document.id,
            VerificationStatus.VERIFIED,
            metadata={
                "classification": classification_result.model_dump(),
            },
        )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _extract_text(raw_bytes: bytes, mime_type: str) -> str:
    if mime_type == "application/pdf":
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise NotImplementedError("Wire up OCR/text extraction for non-PDF documents.")


def _run_classification_sync(document_id: str, expected_type: str, document_text: str):
    import asyncio
    return asyncio.run(extractor.classify_document(document_id, expected_type, document_text))
