"""
UPDATED FLOW (per Maryna/Monique meeting): compares AI-extracted document
values against seller-submitted Intake figures (Business.arr/sde) —
NOT an external tax provider. tax_provider.py is no longer used in this flow.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from app.db.db_enum import VerificationStatus
from app.db.db_model import Business, BusinessFinancials

FINANCIAL_VERIFICATION_RULES_VERSION = "v1"
DEFAULT_TOLERANCE = 0.05


class FieldResult(str, Enum):
    MATCH = "MATCH"
    ACCEPTABLE_DIFFERENCE = "ACCEPTABLE_DIFFERENCE"
    MATERIAL_DISCREPANCY = "MATERIAL_DISCREPANCY"
    MISSING = "MISSING"


@dataclass
class FieldComparison:
    field: str
    reported_value: Optional[float]
    authoritative_value: Optional[float]
    result: FieldResult
    difference_pct: Optional[float] = None


@dataclass
class FinancialVerificationResult:
    business_id: str
    status: VerificationStatus
    rules_version: str
    field_comparisons: list = field(default_factory=list)
    verified_at: Optional[datetime] = None


def _compare_field(field_name: str, reported: Optional[float], authoritative: Optional[float], tolerance: float = DEFAULT_TOLERANCE) -> FieldComparison:
    if reported is None or authoritative is None:
        return FieldComparison(field=field_name, reported_value=reported, authoritative_value=authoritative, result=FieldResult.MISSING)

    diff_pct = 0.0 if authoritative == 0 and reported == 0 else (1.0 if authoritative == 0 else abs(reported - authoritative) / abs(authoritative))

    if diff_pct == 0:
        result = FieldResult.MATCH
    elif diff_pct <= tolerance:
        result = FieldResult.ACCEPTABLE_DIFFERENCE
    else:
        result = FieldResult.MATERIAL_DISCREPANCY

    return FieldComparison(field=field_name, reported_value=reported, authoritative_value=authoritative, result=result, difference_pct=round(diff_pct, 4))


def verify_business_financials(db: Session, business_id: str, extracted_document_fields: dict) -> FinancialVerificationResult:
    """
    extracted_document_fields: output from document_processing/extractor.py,
    e.g. {"revenue": 1980000, "sde": 620000}. Compared against the seller's
    Intake-submitted Business.arr / Business.sde (ground truth is Intake data).
    """
    business = db.query(Business).filter(Business.id == business_id).one()

    comparisons = [
        _compare_field("arr", extracted_document_fields.get("revenue"), business.arr),
        _compare_field("sde", extracted_document_fields.get("sde"), business.sde),
    ]

    status = _resolve_status(comparisons)

    financials = db.query(BusinessFinancials).filter(BusinessFinancials.business_id == business_id).one_or_none()
    if financials is None:
        financials = BusinessFinancials(business_id=business_id)
        db.add(financials)

    financials.verified_arr = extracted_document_fields.get("revenue")
    financials.verified_sde = extracted_document_fields.get("sde")
    financials.verification_status = status
    financials.verification_provider = "ai_document_extraction"
    financials.source = "seller_uploaded_documents"
    financials.verified_at = datetime.utcnow() if status == VerificationStatus.VERIFIED else None
    db.commit()

    return FinancialVerificationResult(
        business_id=business_id, status=status, rules_version=FINANCIAL_VERIFICATION_RULES_VERSION,
        field_comparisons=comparisons, verified_at=financials.verified_at,
    )


def _resolve_status(comparisons: list) -> VerificationStatus:
    if any(c.result in (FieldResult.MATERIAL_DISCREPANCY, FieldResult.MISSING) for c in comparisons):
        return VerificationStatus.REQUIRES_REVIEW
    return VerificationStatus.VERIFIED