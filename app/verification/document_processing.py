from __future__ import annotations

import io

from app.db.db_enum import DocumentType, VerificationStatus
from app.verification.exceptions import DocumentExtractionError
from app.verification.schemas import (
    DetectedDocumentClassification,
    DocumentDecision,
)

SUPPORTED_MIME_TYPE = "application/pdf"


def extract_pdf_text(raw_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise DocumentExtractionError("PDF text extraction failed") from exc
    return text.strip()


def decide_document_status(
    *,
    expected_type: DocumentType,
    classification: DetectedDocumentClassification,
    confidence_threshold: float,
) -> DocumentDecision:
    matches = classification.detected_type == expected_type
    if not matches:
        status = VerificationStatus.REQUIRES_REVIEW
        reason = "document_type_mismatch"
    elif classification.confidence < confidence_threshold:
        status = VerificationStatus.REQUIRES_REVIEW
        reason = "low_confidence"
    else:
        status = VerificationStatus.VERIFIED
        reason = "document_type_verified"
    return DocumentDecision(
        expected_type=expected_type,
        detected_type=classification.detected_type,
        confidence=classification.confidence,
        matches_expected=matches,
        status=status,
        reason_code=reason,
    )
