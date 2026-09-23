from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.db_enum import Industry, SubIndustry, BusinessModel
from app.db.industry_mapping import INDUSTRY_SUB_INDUSTRIES


class IntakeModel(BaseModel):
    """Shared Pydantic behavior for Intake models."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )


class TargetLocation(IntakeModel):
    """
    Standardized location selected through location autocomplete.

    Only fields used by Matchbook are persisted.
    """

    state: str | None = Field(
        default=None,
        max_length=150,
    )

    city: str | None = Field(
        default=None,
        max_length=150,
    )

    county: str | None = Field(
        default=None,
        max_length=150,
    )

    country_code: str | None = Field(
        default=None,
        max_length=20,
    )

    @field_validator(
        "state",
        "city",
        "county",
        "country_code",
    )
    @classmethod
    def blank_string_becomes_none(
            cls,
            value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None

    def has_any_value(self) -> bool:
        return any(
            (
                self.state,
                self.city,
                self.county,
                self.country_code,
            )
        )

class TargetIndustryPreference(IntakeModel):
    industry: Industry

    sub_industries: list[SubIndustry] = Field(
        min_length=1,
    )

    @field_validator("sub_industries")
    @classmethod
    def sub_industries_must_be_unique(
        cls,
        values: list[SubIndustry],
    ) -> list[SubIndustry]:

        if len(values) != len(set(values)):
            raise ValueError(
                "sub_industries cannot contain duplicates"
            )

        return values

    @model_validator(mode="after")
    def validate_sub_industries_belong_to_industry(self):
        allowed = INDUSTRY_SUB_INDUSTRIES.get(
            self.industry,
            frozenset(),
        )

        invalid = [
            sub_industry
            for sub_industry in self.sub_industries
            if sub_industry not in allowed
        ]

        if invalid:
            invalid_values = ", ".join(
                sub_industry.value
                for sub_industry in invalid
            )

            raise ValueError(
                f"Invalid sub-industries for "
                f"'{self.industry.value}': "
                f"{invalid_values}"
            )

        return self
# ============================================================
# OPTIONAL RESPONSE SCHEMAS
#
# Useful if the frontend needs to retrieve the taxonomy from
# the backend rather than duplicating it.
# ============================================================

class SubIndustryOption(BaseModel):
    value: SubIndustry
    label: str


class IndustryOption(BaseModel):
    value: Industry
    label: str
    sub_industries: list[SubIndustryOption]


class BusinessModelOption(BaseModel):
    value: BusinessModel
    label: str
