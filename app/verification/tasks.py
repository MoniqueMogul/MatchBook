from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.db_enum import DocumentType, VerificationStatus
from app.verification.config import VerificationSettings
from app.verification.document_processing import (
    assess_document_gate,
    decide_document_status,
    extract_pdf_text,
)
from app.verification.integrations.classifier import (
    DocumentClassifier,
    LocalDocumentTypeClassifier,
)
from app.verification.integrations.storage import (
    DocumentStorage,
    R2DocumentStorage,
)
from app.verification.repositories import VerificationRepository

log = logging.getLogger("matchbook.verification")


@celery_app.task(
    name="app.verification.tasks.process_document",
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_document(document_id: str) -> None:
    from app.db.session import SessionLocal

    settings = VerificationSettings.from_env()
    session = SessionLocal()
    try:
        run_document_processing(
            session=session,
            document_id=UUID(document_id),
            storage=R2DocumentStorage(settings),
            classifier=LocalDocumentTypeClassifier(),
            confidence_threshold=settings.classification_confidence_threshold,
            max_document_bytes=settings.max_document_bytes,
            max_classifier_characters=settings.max_classifier_characters,
        )
    finally:
        session.close()


def run_document_processing(
    *,
    session: Session,
    document_id: UUID,
    storage: DocumentStorage,
    classifier: DocumentClassifier,
    confidence_threshold: float,
    max_document_bytes: int = 20 * 1024 * 1024,
    max_classifier_characters: int = 50_000,
) -> VerificationStatus | None:
    repository = VerificationRepository(session)
    document = repository.get_document(document_id)
    if document is None:
        return None
    if document.verification_status == VerificationStatus.VERIFIED:
        return VerificationStatus.VERIFIED

    try:
        repository.update_document_status(
            document,
            VerificationStatus.PROCESSING,
            metadata={"failure_code": None},
        )
        session.commit()

        raw_bytes = storage.get_bytes(document.object_key)
        if len(raw_bytes) > max_document_bytes:
            raise ValueError("Downloaded document exceeds the size limit")
        text = extract_pdf_text(raw_bytes)
        if not text:
            repository.update_document_status(
                document,
                VerificationStatus.REQUIRES_REVIEW,
                metadata={
                    "reason_code": "no_extractable_text",
                    "expected_type": _enum_value(document.document_type),
                },
            )
            session.commit()
            return VerificationStatus.REQUIRES_REVIEW

        classification = classifier.classify(text[:max_classifier_characters])
        expected_type = DocumentType(_enum_value(document.document_type))
        gate = assess_document_gate(
            document_text=text,
            expected_type=expected_type,
            expected_business_names=(
                repository.get_expected_business_names(document)
            ),
        )
        decision = decide_document_status(
            expected_type=expected_type,
            classification=classification,
            confidence_threshold=confidence_threshold,
        )
        if (
            decision.status == VerificationStatus.VERIFIED
            and gate.review_reasons
        ):
            decision.status = VerificationStatus.REQUIRES_REVIEW
            decision.reason_code = gate.review_reasons[0]
        verified_at = (
            datetime.now(timezone.utc)
            if decision.status == VerificationStatus.VERIFIED
            else None
        )
        repository.update_document_status(
            document,
            decision.status,
            provider="matchbook_local",
            verified_at=verified_at,
            metadata={
                "expected_type": decision.expected_type.value,
                "detected_type": decision.detected_type.value,
                "confidence": decision.confidence,
                "matches_expected": decision.matches_expected,
                "reason_code": decision.reason_code,
                "classifier_provider": "local_rules_v1",
                "gate_assessment": gate.model_dump(),
            },
        )
        if decision.status == VerificationStatus.VERIFIED:
            repository.create_verification_completed_event(document)
        session.commit()
        return decision.status
    except Exception as exc:
        session.rollback()
        _record_processing_failure(session, document_id, exc)
        log.warning(
            "document_verification_failed",
            extra={
                "event": "document_verification_failed",
                "document_id": str(document_id),
                "error_type": type(exc).__name__,
            },
        )
        return VerificationStatus.FAILED


def _record_processing_failure(
    session: Session,
    document_id: UUID,
    exc: Exception,
) -> None:
    repository = VerificationRepository(session)
    document = repository.get_document(document_id)
    if document is None:
        return
    repository.update_document_status(
        document,
        VerificationStatus.FAILED,
        metadata={
            "failure_code": _failure_code(exc),
            "error_type": type(exc).__name__,
        },
    )
    session.commit()


def _failure_code(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    if "extract" in name or "pdf" in name:
        return "text_extraction_failed"
    if "provider" in name:
        return "provider_failed"
    return "processing_failed"


def _enum_value(value) -> str:
    return getattr(value, "value", value)
