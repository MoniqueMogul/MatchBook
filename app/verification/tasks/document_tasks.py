"""
Document processing pipeline.

Celery is owned by the core/workers team; until wiring exists these run
synchronously from the request. The `process_document_task` signature is
kept as the seam for a future @shared_task wrapper.
"""

from uuid import UUID

from app.db.db_enum import VerificationStatus
from app.verification.document_processing import confidence, extractor, validator
from app.verification.integrations import storage
from app.verification.repositories import documents as documents_repo
from app.verification.services import discrepancy_service


def process_document_task(document_id: str) -> None:
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        document = documents_repo.get_by_id(db, UUID(document_id))
        if document is None:
            return
        if document.verification_status == VerificationStatus.VERIFIED:
            return

        documents_repo.update_status(db, document.id, VerificationStatus.PROCESSING)

        raw_bytes = storage.get_object_bytes(document.bucket_name, document.object_key)
        document_text = _extract_text(raw_bytes, document.mime_type)
        extraction_result = _run_extraction_sync(document_id, document_text)

        if extraction_result.financial_fields:
            validation = validator.validate_financial_fields(extraction_result.financial_fields)
            if not validation.is_valid:
                documents_repo.update_status(db, document.id, VerificationStatus.REQUIRES_REVIEW, metadata={"validation_errors": validation.errors})
                discrepancy_service.flag_for_review(
                    db,
                    discrepancy_service.Discrepancy(
                        entity_type="document", entity_id=document.id,
                        discrepancy_type=discrepancy_service.DiscrepancyType.MISSING_FINANCIAL_RECORDS,
                        evidence={"validation_errors": validation.errors},
                    ),
                )
                return

        if confidence.is_low_confidence(extraction_result.overall_confidence):
            documents_repo.update_status(db, document.id, VerificationStatus.REQUIRES_REVIEW, metadata={"overall_confidence": extraction_result.overall_confidence})
            discrepancy_service.flag_for_review(
                db,
                discrepancy_service.low_confidence_discrepancy(
                    entity_type="document", entity_id=document.id, field_name="overall",
                    confidence=extraction_result.overall_confidence, threshold=confidence.LOW_CONFIDENCE_THRESHOLD,
                ),
            )
            return

        documents_repo.update_status(db, document.id, VerificationStatus.VERIFIED, metadata={"extraction": extraction_result.model_dump()})

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


def _run_extraction_sync(document_id: str, document_text: str):
    import asyncio
    return asyncio.run(extractor.extract_financial_fields(document_id, document_text))