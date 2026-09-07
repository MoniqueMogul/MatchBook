from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AcquisitionEligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class EligibilityRequest(BaseModel):
    buyer_id: UUID
    business_id: UUID


class EligibilityResult(BaseModel):
    buyer_id: UUID
    business_id: UUID
    purchase_price: float
    verified_eligible_liquid_funds: float
    applicable_equity_requirement_pct: float
    required_equity: float
    remaining_liquidity: float
    post_closing_liquidity_requirement: Optional[float] = None
    financing_approved_amount: Optional[float] = None
    status: AcquisitionEligibilityStatus
    reasons: list[str] = []