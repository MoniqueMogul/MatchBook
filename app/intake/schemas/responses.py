from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.db.db_enum import (
    BusinessStatus,
    BuyerType,
    DealPreference,
    RealEstatePreference,
    VerificationStatus,
)
from app.intake.schemas.common import IntakeModel, TargetLocation


class BuyerProfileRead(IntakeModel):
    id: UUID
    user_id: UUID
    buyer_type: BuyerType

    current_industry: str | None = None
    current_position: str | None = None
    business_experience_years: int | None = None
    relevant_experience: str | None = None
    available_hours_per_week: int | None = None

    city: str | None = None
    county: str | None = None
    state: str | None = None
    zip_code: str | None = None

    verification_status: VerificationStatus

    created_at: datetime
    updated_at: datetime


class BuyerPreferencesRead(IntakeModel):
    id: UUID
    buyer_id: UUID

    target_industries: list[str] | None = None
    target_locations: TargetLocation | None = None

    maximum_purchase_price: Decimal | None = None

    minimum_required_sde: Decimal | None = None
    preferred_sde: Decimal | None = None

    minimum_required_arr: Decimal | None = None
    preferred_arr: Decimal | None = None

    preferred_owner_hours_per_week: int | None = None
    required_transition_training_days: int | None = None

    deal_preference: DealPreference | None = None
    real_estate_preference: RealEstatePreference | None = None

    minimum_years_in_operation: int | None = None

    accepts_customer_concentration_above_25_percent: bool | None = None

    preferred_acquisition_timeline: str | None = None

    created_at: datetime
    updated_at: datetime


class SellerProfileRead(IntakeModel):
    id: UUID
    user_id: UUID

    verification_status: VerificationStatus

    created_at: datetime
    updated_at: datetime


class BusinessRead(IntakeModel):
    id: UUID
    seller_id: UUID

    legal_name: str | None = None
    dba: str | None = None

    business_type: str
    industry: str

    city: str
    county: str | None = None
    state: str
    zip_code: str | None = None

    years_in_operation: int | None = None
    number_of_locations: int | None = None
    number_of_routes: int | None = None

    arr: Decimal | None = None
    customer_concentration: Decimal | None = None

    asking_price: Decimal | None = None
    sde: Decimal | None = None

    owner_involvement_hours_per_week: int | None = None
    transition_training_days: int | None = None

    deal_preference: DealPreference | None = None
    preferred_sale_timeline: str | None = None

    verification_status: VerificationStatus
    status: BusinessStatus

    created_at: datetime
    updated_at: datetime


class ReadinessResponse(IntakeModel):
    ready: bool
    missing_fields: tuple[str, ...]
