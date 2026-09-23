from __future__ import annotations

import io
import re

from app.db.db_enum import DocumentType, VerificationStatus
from app.verification.exceptions import DocumentExtractionError
from app.verification.schemas import (
    DetectedDocumentClassification,
    DocumentDecision,
    DocumentGateAssessment,
)

SUPPORTED_MIME_TYPE = "application/pdf"

_PERIOD_DOCUMENT_TYPES = {
    DocumentType.BANK_STATEMENT,
    DocumentType.TAX_RETURN,
    DocumentType.PROFIT_AND_LOSS,
    DocumentType.BALANCE_SHEET,
}

_REPORTING_PERIOD_PATTERN = re.compile(
    r"(?:for (?:the )?(?:year|period) ended|year ended|period ending|"
    r"statement period|tax year|as of).{0,60}\b((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_TAX_FORM_YEAR_PATTERN = re.compile(
    r"\b((?:19|20)\d{2})\b.{0,20}\bform\s+(?:1040|1065|1120|990)\b",
    re.IGNORECASE,
)


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


def assess_document_gate(
    *,
    document_text: str,
    expected_type: DocumentType,
    expected_business_names: list[str] | None,
) -> DocumentGateAssessment:
    normalized_text = _normalize_for_identity(document_text)
    business_match: bool | None = None
    review_reasons: list[str] = []

    usable_names = [
        normalized
        for name in expected_business_names or []
        if (normalized := _normalize_for_identity(name))
    ]
    if usable_names:
        business_match = any(name in normalized_text for name in usable_names)
        if not business_match:
            review_reasons.append("business_identity_not_confirmed")

    reporting_years = sorted(
        {
            int(value)
            for pattern in (
                _REPORTING_PERIOD_PATTERN,
                _TAX_FORM_YEAR_PATTERN,
            )
            for value in pattern.findall(document_text)
        }
    )
    reporting_period: bool | None = None
    if expected_type in _PERIOD_DOCUMENT_TYPES:
        reporting_period = bool(reporting_years)
        if not reporting_period:
            review_reasons.append("reporting_period_not_identified")

    return DocumentGateAssessment(
        readable_text_extracted=bool(document_text.strip()),
        business_identity_match=business_match,
        reporting_period_identified=reporting_period,
        reporting_years=reporting_years,
        review_reasons=review_reasons,
    )


def _normalize_for_identity(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^a-z0-9]+", " ", value.lower()),
    ).strip()
