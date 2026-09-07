from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.db.db_enum import FundingSource, LenderApprovedStatus


class FinancingRequest(BaseModel):
    buyer_id: UUID
    business_id: UUID
    financing_requested_amount: float
    lender_name: Optional[str] = None


class FinancingStatusOut(BaseModel):
    buyer_id: UUID
    funding_source: Optional[FundingSource]
    financing_requested_amount: Optional[float]
    financing_approved_amount: Optional[float]
    lender_name: Optional[str]
    lender_approval_status: Optional[LenderApprovedStatus]

    class Config:
        from_attributes = True