from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_model import Business, BuyerFinancials
from app.verification.schemas.eligibility import AcquisitionEligibilityStatus, EligibilityResult

DEFAULT_EQUITY_REQUIREMENT_PCT = 0.10
DEFAULT_POST_CLOSING_LIQUIDITY_REQUIREMENT_PCT = 0.10


def calculate_eligibility(
    db: Session,
    buyer_id: UUID,
    business_id: UUID,
    equity_requirement_pct: Optional[float] = None,
    post_closing_liquidity_pct: Optional[float] = None,
) -> EligibilityResult:
    business = db.query(Business).filter(Business.id == business_id).one()
    buyer_financials = db.query(BuyerFinancials).filter(BuyerFinancials.buyer_id == buyer_id).one()

    purchase_price = business.asking_price
    verified_funds = buyer_financials.verified_cash_amount or 0.0
    equity_pct = equity_requirement_pct or DEFAULT_EQUITY_REQUIREMENT_PCT
    liquidity_pct = post_closing_liquidity_pct or DEFAULT_POST_CLOSING_LIQUIDITY_REQUIREMENT_PCT

    required_equity = purchase_price * equity_pct
    remaining_liquidity = verified_funds - required_equity
    post_closing_requirement = buyer_financials.financing_approved_amount * liquidity_pct if buyer_financials.financing_approved_amount else None

    reasons = []
    if remaining_liquidity < 0:
        status = AcquisitionEligibilityStatus.NOT_ELIGIBLE
        reasons.append("Verified liquid funds are insufficient to cover required equity.")
    elif post_closing_requirement is not None and remaining_liquidity < post_closing_requirement:
        status = AcquisitionEligibilityStatus.REQUIRES_REVIEW
        reasons.append("Remaining liquidity falls below the post-closing liquidity requirement.")
    else:
        status = AcquisitionEligibilityStatus.ELIGIBLE

    return EligibilityResult(
        buyer_id=buyer_id, business_id=business_id, purchase_price=purchase_price,
        verified_eligible_liquid_funds=verified_funds, applicable_equity_requirement_pct=equity_pct,
        required_equity=required_equity, remaining_liquidity=remaining_liquidity,
        post_closing_liquidity_requirement=post_closing_requirement,
        financing_approved_amount=buyer_financials.financing_approved_amount, status=status, reasons=reasons,
    )


def calculate_eligible_liquid_funds(account_balances: list, restricted_amount: float = 0.0) -> float:
    total = sum(a["balance"] for a in account_balances if a.get("eligible", True))
    return max(total - restricted_amount, 0.0)