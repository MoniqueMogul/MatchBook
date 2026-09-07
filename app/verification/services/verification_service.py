"""
Writes to verification_* columns on User/Business/BusinessFinancials —
shared models in app.db. Per team decision, verification owns the trigger;
intake still owns intake data entry.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.db.db_enum import VerificationStatus
from app.db.db_model import Business, BusinessFinancials, User
from app.verification.integrations import kyc_provider
from app.verification.integrations.kyc_provider import (
    DiditSessionStatus,
    NormalizedVerificationResult,
    VerificationSession,
)

_STATUS_MAP = {
    DiditSessionStatus.NOT_STARTED: VerificationStatus.UNVERIFIED,
    DiditSessionStatus.IN_PROGRESS: VerificationStatus.PENDING,
    DiditSessionStatus.IN_REVIEW: VerificationStatus.REQUIRES_REVIEW,
    DiditSessionStatus.APPROVED: VerificationStatus.VERIFIED,
    DiditSessionStatus.DECLINED: VerificationStatus.FAILED,
    DiditSessionStatus.RESUBMISSION_REQUESTED: VerificationStatus.REQUIRES_REVIEW,
}


async def start_user_kyc(db: Session, user_id: str) -> VerificationSession:
    session = await kyc_provider.create_session(workflow_type="individual_kyc", vendor_data=user_id)
    user = db.query(User).filter(User.id == user_id).one()
    user.verification_status = VerificationStatus.PENDING
    user.verification_provider = "didit"
    user.provider_reference = session.session_id
    db.commit()
    return session


async def start_business_existence_check(db: Session, business_id: str) -> VerificationSession:
    session = await kyc_provider.create_session(workflow_type="ein_check", vendor_data=business_id)
    business = db.query(Business).filter(Business.id == business_id).one()
    business.verification_status = VerificationStatus.PENDING
    db.commit()
    return session


async def start_full_kyb(db: Session, business_id: str) -> VerificationSession:
    return await kyc_provider.create_session(workflow_type="full_kyb", vendor_data=business_id)


def handle_verification_result(db: Session, result: NormalizedVerificationResult) -> None:
    status = _STATUS_MAP[result.status]

    if result.workflow_type == "individual_kyc":
        _apply_to_user(db, result, status)
    elif result.workflow_type == "ein_check":
        _apply_to_business(db, result, status)
    elif result.workflow_type == "full_kyb":
        _apply_to_business_financials(db, result, status)

    db.commit()


def _apply_to_user(db: Session, result: NormalizedVerificationResult, status: VerificationStatus) -> None:
    user = db.query(User).filter(User.provider_reference == result.session_id).one_or_none()
    if user is None:
        return
    user.verification_status = status
    user.provider_reference = result.session_id
    user.verified_at = datetime.utcnow() if status == VerificationStatus.VERIFIED else None


def _apply_to_business(db: Session, result: NormalizedVerificationResult, status: VerificationStatus) -> None:
    business = db.query(Business).filter(Business.id == result.vendor_data).one_or_none()
    if business is None:
        return
    business.verification_status = status


def _apply_to_business_financials(db: Session, result: NormalizedVerificationResult, status: VerificationStatus) -> None:
    financials = db.query(BusinessFinancials).filter(BusinessFinancials.business_id == result.vendor_data).one_or_none()
    if financials is None:
        return
    financials.verification_status = status
    financials.verification_provider = "didit"
    financials.provider_reference = result.session_id
    financials.verified_at = datetime.utcnow() if status == VerificationStatus.VERIFIED else None


def get_status(db: Session, entity_type: str, entity_id: str) -> Optional[str]:
    model_map = {"user": User, "business": Business, "business_financials": BusinessFinancials}
    model = model_map.get(entity_type)
    if model is None:
        raise ValueError(f"Unknown entity_type: {entity_type}")
    entity = db.query(model).filter(model.id == entity_id).one_or_none()
    return entity.verification_status if entity else None