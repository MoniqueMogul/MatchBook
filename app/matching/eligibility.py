from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.matching.config import PRICE_TOLERANCE


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    failed_constraints: list[str]


def _normalize_text(
    value: str | None,
) -> str | None:
    """
    Normalize text for deterministic comparisons.
    """
    if value is None:
        return None

    normalized = value.strip().lower()

    return normalized or None


# ============================================================
# INDUSTRY
# ============================================================


def check_industry_eligibility(
    target_industries: list[str] | None,
    business_industry: str | None,
) -> bool:
    """
    Industry is a V1 hard eligibility filter.
    """
    if not target_industries:
        return True

    normalized_business = _normalize_text(
        business_industry
    )

    if normalized_business is None:
        return False

    normalized_targets = {
        normalized
        for industry in target_industries
        if (
            normalized := _normalize_text(
                industry
            )
        ) is not None
    }

    return (
        normalized_business
        in normalized_targets
    )


# ============================================================
# GEOGRAPHY
# ============================================================


def check_geography_eligibility(
    target_locations: dict[str, Any] | None,
    *,
    business_city: str | None,
    business_county: str | None,
    business_state: str | None,
) -> bool:
    """
    Geography is a deterministic V1 hard filter.

    Supported fields:
        state
        city
        county
    """
    if not target_locations:
        return True

    business_location = {
        "city": _normalize_text(
            business_city
        ),
        "county": _normalize_text(
            business_county
        ),
        "state": _normalize_text(
            business_state
        ),
    }

    for field in (
        "state",
        "city",
        "county",
    ):
        requested = target_locations.get(
            field
        )

        if requested is None:
            continue

        if isinstance(
            requested,
            str,
        ):
            normalized = _normalize_text(
                requested
            )

            acceptable_values = (
                {normalized}
                if normalized is not None
                else set()
            )

        elif isinstance(
            requested,
            list,
        ):
            acceptable_values = {
                normalized
                for value in requested
                if isinstance(
                    value,
                    str,
                )
                and (
                    normalized
                    := _normalize_text(
                        value
                    )
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


# ============================================================
# PURCHASE PRICE
# ============================================================


def calculate_absolute_price_ceiling(
    maximum_purchase_price: Decimal,
    price_tolerance: float = PRICE_TOLERANCE,
) -> Decimal:
    """
    Absolute price ceiling:

        max purchase price × (1 + tolerance)
    """
    tolerance = Decimal(
        str(
            price_tolerance
        )
    )

    return (
        maximum_purchase_price
        * (
            Decimal("1")
            + tolerance
        )
    )


def check_purchase_price_eligibility(
    maximum_purchase_price: Decimal | None,
    asking_price: Decimal | None,
    price_tolerance: float = PRICE_TOLERANCE,
) -> bool:
    """
    V1 hard purchase-price filter.
    """
    if maximum_purchase_price is None:
        return True

    if asking_price is None:
        return False

    absolute_ceiling = (
        calculate_absolute_price_ceiling(
            maximum_purchase_price,
            price_tolerance,
        )
    )

    return (
        asking_price
        <= absolute_ceiling
    )


# ============================================================
# MINIMUM SDE
# ============================================================


def check_sde_eligibility(
    minimum_sde: Decimal | None,
    seller_sde: Decimal | None,
) -> bool:
    """
    Seller must meet buyer's minimum required SDE.
    """
    if minimum_sde is None:
        return True

    if seller_sde is None:
        return False

    return (
        seller_sde
        >= minimum_sde
    )


# ============================================================
# MINIMUM ARR
# ============================================================


def check_arr_eligibility(
    minimum_arr: Decimal | None,
    seller_arr: Decimal | None,
) -> bool:
    """
    Seller must meet buyer's minimum required ARR.

    ARR remains a scoring dimension after the candidate passes
    this hard minimum requirement.
    """
    if (
        minimum_arr is None
        or minimum_arr <= Decimal("0")
    ):
        return True

    if seller_arr is None:
        return False

    return (
        seller_arr
        >= minimum_arr
    )


# ============================================================
# MINIMUM YEARS IN OPERATION
# ============================================================


def check_years_in_operation_eligibility(
    minimum_years: int | None,
    business_years: int | None,
) -> bool:
    """
    Seller/business must meet the buyer's minimum years
    in operation requirement.
    """
    if (
        minimum_years is None
        or minimum_years <= 0
    ):
        return True

    if business_years is None:
        return False

    return (
        business_years
        >= minimum_years
    )


# ============================================================
# COMPLETE V1 ELIGIBILITY
# ============================================================


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

    # Added V1 constraints.
    minimum_arr: Decimal | None = None,
    seller_arr: Decimal | None = None,
    minimum_years_in_operation: int | None = None,
    business_years_in_operation: int | None = None,
) -> EligibilityResult:
    """
    Evaluate V1 hard eligibility constraints.

    Current sequence:

        Industry
        Geography
        Purchase Price
        Minimum SDE
        Minimum ARR
        Minimum Years in Operation

    A candidate that fails any hard constraint does not proceed
    to compatibility scoring.
    """
    failures: list[str] = []

    if not check_industry_eligibility(
        target_industries,
        business_industry,
    ):
        failures.append(
            "industry"
        )

    if not check_geography_eligibility(
        target_locations,
        business_city=business_city,
        business_county=business_county,
        business_state=business_state,
    ):
        failures.append(
            "geography"
        )

    if not check_purchase_price_eligibility(
        maximum_purchase_price,
        asking_price,
    ):
        failures.append(
            "purchase_price"
        )

    if not check_sde_eligibility(
        minimum_sde,
        seller_sde,
    ):
        failures.append(
            "sde"
        )

    if not check_arr_eligibility(
        minimum_arr,
        seller_arr,
    ):
        failures.append(
            "arr"
        )

    if not check_years_in_operation_eligibility(
        minimum_years_in_operation,
        business_years_in_operation,
    ):
        failures.append(
            "years_in_operation"
        )

    return EligibilityResult(
        eligible=(
            len(
                failures
            )
            == 0
        ),
        failed_constraints=failures,
    )