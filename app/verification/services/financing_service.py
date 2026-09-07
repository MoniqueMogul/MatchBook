from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import LenderApprovedStatus
from app.db.db_model import BuyerFinancials
from app.verification.integrations import lending_partner
from app.verification.schemas.financing import FinancingRequest, FinancingStatusOut


async def request_financing(db: Session, request: FinancingRequest) -> FinancingStatusOut:
    buyer_financials = db.query(BuyerFinancials).filter(BuyerFinancials.buyer_id == request.buyer_id).one()

    submission = await lending_partner.submit_financing_request(
        buyer_id=str(request.buyer_id), business_id=str(request.business_id),
        amount_requested=request.financing_requested_amount, lender_name=request.lender_name,
    )

    buyer_financials.financing_requested_amount = request.financing_requested_amount
    buyer_financials.lender_name = submission.get("lender_name", request.lender_name)
    buyer_financials.lender_approval_status = LenderApprovedStatus.PENDING
    db.commit()
    db.refresh(buyer_financials)
    return FinancingStatusOut.model_validate(buyer_financials)


async def handle_lender_decision(db: Session, buyer_id: UUID, decision: dict) -> None:
    buyer_financials = db.query(BuyerFinancials).filter(BuyerFinancials.buyer_id == buyer_id).one()
    buyer_financials.lender_approval_status = LenderApprovedStatus(decision["status"])
    buyer_financials.financing_approved_amount = decision.get("approved_amount")
    db.commit()


async def get_financing_status(db: Session, buyer_id: UUID) -> FinancingStatusOut:
    buyer_financials = db.query(BuyerFinancials).filter(BuyerFinancials.buyer_id == buyer_id).one()
    return FinancingStatusOut.model_validate(buyer_financials)