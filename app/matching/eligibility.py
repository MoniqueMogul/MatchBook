from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.matching.config import PRICE_TOLERANCE


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    failed_constraints: list[str]


def _normalize_text(value: str | None) -> str | None:
    """
    Normalize text values for deterministic matching.
    """
    if value is None:
        return None

    normalized = value.strip().lower()

    return normalized or None


def check_industry_eligibility(
    target_industries: list[str] | None,
    business_industry: str | None,
) -> bool:
    """
    Industry is a V1 hard filter.

    A business passes when its industry matches one of the buyer's
    selected target industries.

    If the buyer has no configured target industries, the constraint
    is treated as unrestricted.
    """
    if not target_industries:
        return True

    normalized_business_industry = _normalize_text(
        business_industry
    )

    if normalized_business_industry is None:
        return False

    normalized_targets = {
        normalized
        for industry in target_industries
        if (
            normalized := _normalize_text(industry)
        ) is not None
    }

    return normalized_business_industry in normalized_targets


def check_geography_eligibility(
    target_locations: dict[str, Any] | None,
    *,
    business_city: str | None,
    business_county: str | None,
    business_state: str | None,
) -> bool:
    """
    Geography is a deterministic V1 hard filter.

    Supported V1 buyer location fields:
    - state
    - city
    - county

    Each configured buyer requirement must be satisfied.
    """
    if not target_locations:
        return True

    business_location = {
        "city": _normalize_text(business_city),
        "county": _normalize_text(business_county),
        "state": _normalize_text(business_state),
    }

    for field in ("state", "city", "county"):
        requested_value = target_locations.get(field)

        if requested_value is None:
            continue

        if isinstance(requested_value, str):
            normalized_value = _normalize_text(
                requested_value
            )

            acceptable_values = (
                {normalized_value}
                if normalized_value is not None
                else set()
            )

        elif isinstance(requested_value, list):
            acceptable_values = {
                normalized
                for value in requested_value
                if isinstance(value, str)
                and (
                    normalized := _normalize_text(value)
                ) is not None
            }

        else:
            continue

        if (
            acceptable_values
            and business_location[field]
            not in acceptable_values
        ):
            return False

    return True


def calculate_absolute_price_ceiling(
    maximum_purchase_price: Decimal,
    price_tolerance: float = PRICE_TOLERANCE,
) -> Decimal:
    """
    Calculate the V1 absolute purchase-price ceiling.

    Absolute Ceiling =
        Maximum Purchase Price × (1 + tolerance)

    V1 tolerance = 15%.
    """
    tolerance = Decimal(str(price_tolerance))

    return maximum_purchase_price * (
        Decimal("1") + tolerance
    )


def check_purchase_price_eligibility(
    maximum_purchase_price: Decimal | None,
    asking_price: Decimal | None,
    price_tolerance: float = PRICE_TOLERANCE,
) -> bool:
    """
    Purchase price is a V1 hard filter.

    Candidate passes when:

        asking_price <= maximum_purchase_price × 1.15

    If the buyer has no maximum configured, the constraint is
    treated as unrestricted.
    """
    if maximum_purchase_price is None:
        return True

    if asking_price is None:
        return False

    absolute_ceiling = calculate_absolute_price_ceiling(
        maximum_purchase_price,
        price_tolerance,
    )

    return asking_price <= absolute_ceiling


def check_sde_eligibility(
    minimum_sde: Decimal | None,
    seller_sde: Decimal | None,
) -> bool:
    """
    SDE is a V1 hard filter.

    Candidate passes when:

        seller_sde >= buyer minimum SDE

    If the buyer has no minimum SDE configured, the constraint
    is treated as unrestricted.
    """
    if minimum_sde is None:
        return True

    if seller_sde is None:
        return False

    return seller_sde >= minimum_sde


def evaluate_eligibility(
    *,
    target_industries: list[str] | None,
    target_locations: dict[str, Any] | None,
    maximum_purchase_price: Decimal | None,
    minimum_sde: Decimal | None,
    business_industry: str | None,
    business_city: str | None,
    business_county: str | None,
    business_state: str | None,
    asking_price: Decimal | None,
    seller_sde: Decimal | None,
) -> EligibilityResult:
    """
    Evaluate all V1 hard eligibility constraints.

    V1 flow:
        Industry
        Geography
        Purchase Price Ceiling
        Minimum SDE

    Any failed required hard filter rejects the candidate before
    compatibility scoring.
    """
    failures: list[str] = []

    if not check_industry_eligibility(
        target_industries,
        business_industry,
    ):
        failures.append("industry")

    if not check_geography_eligibility(
        target_locations,
        business_city=business_city,
        business_county=business_county,
        business_state=business_state,
    ):
        failures.append("geography")

    if not check_purchase_price_eligibility(
        maximum_purchase_price,
        asking_price,
    ):
        failures.append("purchase_price")

    if not check_sde_eligibility(
        minimum_sde,
        seller_sde,
    ):
        failures.append("sde")

    return EligibilityResult(
        eligible=len(failures) == 0,
        failed_constraints=failures,
    )