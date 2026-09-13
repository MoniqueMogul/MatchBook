from typing import Literal

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
    """A standardized location selected from LocationIQ autocomplete."""

    provider: Literal["locationiq"]
    place_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=500)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    city: str | None = Field(default=None, max_length=150)
    county: str | None = Field(default=None, max_length=150)
    state: str | None = Field(default=None, max_length=150)
    country: str | None = Field(default=None, max_length=150)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("state", "city", "county", "country")
    @classmethod
    def blank_string_becomes_none(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    @field_validator("country_code", mode="before")
    @classmethod
    def uppercase_country_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    def has_any_value(self) -> bool:
        return bool(self.provider and self.place_id and self.display_name)
