from decimal import Decimal

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from app.db.db_enum import (
    DealPreference,
    RealEstatePreference,
)

from app.intake.schemas.common import (
    IntakeModel,
    TargetLocation,
)


class BuyerPreferencesUpsert(IntakeModel):
    """
    Buyer acquisition preferences.

    Fields remain optional because a buyer can build
    a draft profile incrementally.

    Matching readiness is checked separately.
    """

    target_industries: list[str] | None = None

    target_locations: TargetLocation | None = None

    maximum_purchase_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=15,
        decimal_places=2,
    )

    minimum_required_sde: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    preferred_sde: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    minimum_required_arr: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    preferred_arr: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    preferred_owner_hours_per_week: int | None = Field(
        default=None,
        ge=0,
        le=168,
    )

    required_transition_training_days: int | None = Field(
        default=None,
        ge=0,
    )

    deal_preference: DealPreference | None = None

    real_estate_preference: RealEstatePreference | None = None

    minimum_years_in_operation: int | None = Field(
        default=None,
        ge=0,
    )

    accepts_customer_concentration_above_25_percent: bool | None = None

    preferred_acquisition_timeline: str | None = Field(
        default=None,
        max_length=100,
    )

    @field_validator("target_industries")
    @classmethod
    def clean_target_industries(
        cls,
        industries: list[str] | None,
    ) -> list[str] | None:

        if industries is None:
            return None

        cleaned: list[str] = []
        seen: set[str] = set()

        for raw in industries:
            industry = raw.strip()

            if not industry:
                continue

            key = industry.casefold()

            if key not in seen:
                cleaned.append(industry)
                seen.add(key)

        return cleaned or None

    @field_validator("preferred_acquisition_timeline")
    @classmethod
    def blank_timeline_becomes_none(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None

    @model_validator(mode="after")
    def validate_preference_ranges(
        self,
    ) -> "BuyerPreferencesUpsert":

        if (
            self.minimum_required_sde is not None
            and self.preferred_sde is not None
            and self.preferred_sde < self.minimum_required_sde
        ):
            raise ValueError(
                "preferred_sde must be greater than "
                "or equal to minimum_required_sde"
            )

        if (
            self.minimum_required_arr is not None
            and self.preferred_arr is not None
            and self.preferred_arr < self.minimum_required_arr
        ):
            raise ValueError(
                "preferred_arr must be greater than "
                "or equal to minimum_required_arr"
            )

        return self