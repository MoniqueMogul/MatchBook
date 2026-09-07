from dataclasses import dataclass, field
from datetime import datetime

from app.verification.schemas.extraction import ExtractedFinancialFields

MIN_REASONABLE_YEAR = 2000
MAX_REASONABLE_REVENUE = 1_000_000_000


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list = field(default_factory=list)


def validate_financial_fields(fields: ExtractedFinancialFields) -> ValidationResult:
    errors = []
    if fields.year is not None:
        current_year = datetime.utcnow().year
        if not (MIN_REASONABLE_YEAR <= fields.year <= current_year):
            errors.append(f"year {fields.year} outside reasonable range")

    for name, value in [("revenue", fields.revenue), ("sde", fields.sde), ("ebitda", fields.ebitda)]:
        if value is not None:
            if value < 0:
                errors.append(f"{name} cannot be negative: {value}")
            if value > MAX_REASONABLE_REVENUE:
                errors.append(f"{name} exceeds sanity ceiling: {value}")

    if fields.reporting_period_start and fields.reporting_period_end:
        try:
            start = datetime.fromisoformat(fields.reporting_period_start)
            end = datetime.fromisoformat(fields.reporting_period_end)
            if start >= end:
                errors.append("reporting_period_start must be before reporting_period_end")
        except ValueError:
            errors.append("reporting period dates are not valid ISO format")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)