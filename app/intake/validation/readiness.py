from dataclasses import dataclass

from app.intake.schemas.business import BusinessCreate
from app.intake.schemas.buyer_preferences import BuyerPreferencesUpsert


@dataclass(frozen=True)
class ReadinessResult:
    """
    Whether a valid draft contains every field
    required by V1, including completion progress.
    """

    ready: bool
    completion_percentage: int
    completed_fields: int
    total_required_fields: int
    missing_fields: tuple[str, ...]


def _build_readiness_result(
    missing: list[str],
    total_required_fields: int,
) -> ReadinessResult:
    """
    Build the standard readiness response.
    """

    completed_fields = (
        total_required_fields
        - len(missing)
    )

    completion_percentage = round(
        (completed_fields / total_required_fields)
        * 100
    )

    return ReadinessResult(
        ready=not missing,
        completion_percentage=completion_percentage,
        completed_fields=completed_fields,
        total_required_fields=total_required_fields,
        missing_fields=tuple(missing),
    )


def buyer_preferences_readiness(
    preferences: BuyerPreferencesUpsert,
) -> ReadinessResult:

    missing: list[str] = []

    if not preferences.target_industry_preferences:
        missing.append(
            "target_industry_preferences"
        )

    if not preferences.target_business_models:
        missing.append(
            "target_business_models"
        )

    if not preferences.target_business_types:
        missing.append(
            "target_business_types"
        )

    if not preferences.target_locations or not any(
        location.has_any_value()
        for location in preferences.target_locations
    ):
        missing.append("target_locations")

    if preferences.maximum_purchase_price is None:
        missing.append("maximum_purchase_price")

    if preferences.minimum_required_sde is None:
        missing.append("minimum_required_sde")

    if preferences.preferred_sde is None:
        missing.append("preferred_sde")

    if preferences.minimum_required_arr is None:
        missing.append("minimum_required_arr")

    if preferences.preferred_arr is None:
        missing.append("preferred_arr")

    if preferences.preferred_owner_hours_per_week is None:
        missing.append(
            "preferred_owner_hours_per_week"
        )

    if preferences.required_transition_training_days is None:
        missing.append(
            "required_transition_training_days"
        )

    if preferences.deal_preference is None:
        missing.append("deal_preference")

    if (
        preferences
        .accepts_customer_concentration_above_25_percent
        is None
    ):
        missing.append(
            "accepts_customer_concentration_above_25_percent"
        )

    if preferences.preferred_acquisition_timeline is None:
        missing.append(
            "preferred_acquisition_timeline"
        )

    return _build_readiness_result(
        missing=missing,
        total_required_fields=12,
    )


def business_readiness(
    business: BusinessCreate,
) -> ReadinessResult:

    missing: list[str] = []

    if business.asking_price is None:
        missing.append("asking_price")

    if business.sde is None:
        missing.append("sde")

    if business.arr is None:
        missing.append("arr")

    if business.customer_concentration is None:
        missing.append("customer_concentration")

    if business.owner_involvement_hours_per_week is None:
        missing.append(
            "owner_involvement_hours_per_week"
        )

    if business.transition_training_days is None:
        missing.append(
            "transition_training_days"
        )

    if business.deal_preference is None:
        missing.append("deal_preference")

    if business.preferred_sale_timeline is None:
        missing.append(
            "preferred_sale_timeline"
        )

    return _build_readiness_result(
        missing=missing,
        total_required_fields=8,
    )