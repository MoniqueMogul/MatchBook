from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from app.db.db_enum import (
    BusinessModel,
    BusinessType,
    DealPreference,
    Industry,
    SubIndustry,
)
from app.db.industry_mapping import INDUSTRY_SUB_INDUSTRIES
from app.intake.schemas.common import IntakeModel


# Only actual free-text fields belong here.
_OPTIONAL_TEXT_FIELDS = (
    "legal_name",
    "dba",
    "county",
    "zip_code",
    "preferred_sale_timeline",
)


_REQUIRED_TEXT_FIELDS = (
    "city",
    "state",
)


class BusinessCreate(IntakeModel):
    """Seller business data used to create a draft business."""

    legal_name: str | None = Field(
        default=None,
        max_length=255,
    )

    dba: str | None = Field(
        default=None,
        max_length=255,
    )

    # Legal structure: LLC, corporation, partnership, etc.
    business_type: BusinessType

    # Business classification
    industry: Industry
    sub_industry: SubIndustry
    business_model: BusinessModel

    city: str = Field(
        min_length=1,
        max_length=100,
    )

    county: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str = Field(
        min_length=1,
        max_length=100,
    )

    zip_code: str | None = Field(
        default=None,
        max_length=20,
    )

    years_in_operation: int | None = Field(
        default=None,
        ge=0,
    )

    number_of_locations: int | None = Field(
        default=None,
        ge=0,
    )

    number_of_routes: int | None = Field(
        default=None,
        ge=0,
    )

    arr: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    customer_concentration: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=5,
        decimal_places=2,
    )

    asking_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=15,
        decimal_places=2,
    )

    sde: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    owner_involvement_hours_per_week: int | None = Field(
        default=None,
        ge=0,
        le=168,
    )

    transition_training_days: int | None = Field(
        default=None,
        ge=0,
    )

    deal_preference: DealPreference | None = None

    preferred_sale_timeline: str | None = Field(
        default=None,
        max_length=50,
    )

    @field_validator(*_OPTIONAL_TEXT_FIELDS)
    @classmethod
    def blank_optional_string_becomes_none(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None

    @field_validator(*_REQUIRED_TEXT_FIELDS)
    @classmethod
    def required_string_cannot_be_blank(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "field cannot be blank"
            )

        return value

    @model_validator(mode="after")
    def validate_industry_classification(self):
        allowed_sub_industries = INDUSTRY_SUB_INDUSTRIES.get(
            self.industry
        )

        if allowed_sub_industries is None:
            raise ValueError(
                f"No sub-industry configuration exists for "
                f"industry '{self.industry.value}'."
            )

        if self.sub_industry not in allowed_sub_industries:
            raise ValueError(
                f"Sub-industry '{self.sub_industry.value}' "
                f"is not valid for industry "
                f"'{self.industry.value}'."
            )

        return self


class BusinessUpdate(IntakeModel):
    """Partial update for an existing business."""

    legal_name: str | None = Field(
        default=None,
        max_length=255,
    )

    dba: str | None = Field(
        default=None,
        max_length=255,
    )

    business_type: BusinessType | None = None

    industry: Industry | None = None
    sub_industry: SubIndustry | None = None
    business_model: BusinessModel | None = None

    city: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    county: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    zip_code: str | None = Field(
        default=None,
        max_length=20,
    )

    years_in_operation: int | None = Field(
        default=None,
        ge=0,
    )

    number_of_locations: int | None = Field(
        default=None,
        ge=0,
    )

    number_of_routes: int | None = Field(
        default=None,
        ge=0,
    )

    arr: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    customer_concentration: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=5,
        decimal_places=2,
    )

    asking_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=15,
        decimal_places=2,
    )

    sde: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=15,
        decimal_places=2,
    )

    owner_involvement_hours_per_week: int | None = Field(
        default=None,
        ge=0,
        le=168,
    )

    transition_training_days: int | None = Field(
        default=None,
        ge=0,
    )

    deal_preference: DealPreference | None = None

    preferred_sale_timeline: str | None = Field(
        default=None,
        max_length=50,
    )

    @field_validator(*_OPTIONAL_TEXT_FIELDS)
    @classmethod
    def blank_optional_string_becomes_none(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None

    @field_validator(*_REQUIRED_TEXT_FIELDS)
    @classmethod
    def required_field_cannot_be_blank_if_provided(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError(
                "field cannot be blank"
            )

        return value