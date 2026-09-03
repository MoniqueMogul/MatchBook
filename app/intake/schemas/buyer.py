from pydantic import Field, field_validator

from app.db.db_enum import BuyerType
from app.intake.schemas.common import IntakeModel


_OPTIONAL_TEXT_FIELDS = (
    "current_industry",
    "current_position",
    "relevant_experience",
    "city",
    "county",
    "state",
    "zip_code",
)


class BuyerProfileCreate(IntakeModel):
    """Data accepted when creating a buyer profile."""

    buyer_type: BuyerType

    current_industry: str | None = Field(
        default=None,
        max_length=150,
    )

    current_position: str | None = Field(
        default=None,
        max_length=150,
    )

    business_experience_years: int | None = Field(
        default=None,
        ge=0,
    )

    relevant_experience: str | None = None

    available_hours_per_week: int | None = Field(
        default=None,
        ge=0,
        le=168,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    county: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        max_length=100,
    )

    zip_code: str | None = Field(
        default=None,
        max_length=20,
    )

    @field_validator(*_OPTIONAL_TEXT_FIELDS)
    @classmethod
    def blank_string_becomes_none(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None


class BuyerProfileUpdate(IntakeModel):
    """Partial update for an existing buyer profile."""

    buyer_type: BuyerType | None = None

    current_industry: str | None = Field(
        default=None,
        max_length=150,
    )

    current_position: str | None = Field(
        default=None,
        max_length=150,
    )

    business_experience_years: int | None = Field(
        default=None,
        ge=0,
    )

    relevant_experience: str | None = None

    available_hours_per_week: int | None = Field(
        default=None,
        ge=0,
        le=168,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    county: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        max_length=100,
    )

    zip_code: str | None = Field(
        default=None,
        max_length=20,
    )

    @field_validator(*_OPTIONAL_TEXT_FIELDS)
    @classmethod
    def blank_string_becomes_none(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None