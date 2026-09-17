from pydantic import BaseModel, ConfigDict, Field, field_validator


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
