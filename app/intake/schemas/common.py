from pydantic import BaseModel, ConfigDict, field_validator


class IntakeModel(BaseModel):
    """Shared Pydantic behavior for Intake models."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )


class TargetLocation(IntakeModel):
    """Structured V1 geography preference."""

    state: str | None = None
    city: str | None = None
    county: str | None = None

    @field_validator("state", "city", "county")
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
            )
        )