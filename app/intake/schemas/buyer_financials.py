from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.db.db_enum import (
    FundingSource,
    LenderApprovedStatus,
    VerificationStatus,
)
from app.intake.schemas.common import IntakeModel


class BuyerFinancialsUpsert(IntakeModel):
    """
    Buyer-supplied financial capability information.

    Provider-controlled verification fields are intentionally
    excluded from this request model.
    """

    funding_source: FundingSource | None = None

    reported_cash_available: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    financing_requested_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    lender_name: str | None = Field(
        default=None,
        max_length=255,
    )


class BuyerFinancialsRead(IntakeModel):
    id: UUID
    buyer_id: UUID

    funding_source: FundingSource | None

    reported_cash_available: Decimal | None
    verified_cash_amount: Decimal | None

    financing_requested_amount: Decimal | None
    financing_approved_amount: Decimal | None

    lender_name: str | None
    lender_approval_status: LenderApprovedStatus | None

    verification_status: VerificationStatus
    verified_at: datetime | None

    created_at: datetime
    updated_at: datetime
