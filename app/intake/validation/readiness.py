from dataclasses import dataclass

from app.intake.schemas.business import (
    BusinessCreate,
)

from app.intake.schemas.buyer_preferences import (
    BuyerPreferencesUpsert,
)


@dataclass(frozen=True)
class ReadinessResult:
    """
    Whether a valid draft contains every
    field required by V1 matching.
    """

    ready: bool
    missing_fields: tuple[str, ...]


def buyer_preferences_readiness(
    preferences: BuyerPreferencesUpsert,
) -> ReadinessResult:

    missing: list[str] = []

    if not preferences.target_industries:
        missing.append(
            "target_industries"
        )

    if (
        preferences.target_locations is None
        or not preferences
        .target_locations
        .has_any_value()
    ):
        missing.append(
            "target_locations"
        )

    if preferences.maximum_purchase_price is None:
        missing.append(
            "maximum_purchase_price"
        )

    if preferences.minimum_required_sde is None:
        missing.append(
            "minimum_required_sde"
        )

    if preferences.preferred_sde is None:
        missing.append(
            "preferred_sde"
        )

    if (
        preferences
        .preferred_owner_hours_per_week
        is None
    ):
        missing.append(
            "preferred_owner_hours_per_week"
        )

    if (
        preferences
        .required_transition_training_days
        is None
    ):
        missing.append(
            "required_transition_training_days"
        )

    if preferences.deal_preference is None:
        missing.append(
            "deal_preference"
        )

    return ReadinessResult(
        ready=not missing,
        missing_fields=tuple(missing),
    )


def business_readiness(
    business: BusinessCreate,
) -> ReadinessResult:

    missing: list[str] = []

    if business.asking_price is None:
        missing.append(
            "asking_price"
        )

    if business.sde is None:
        missing.append(
            "sde"
        )

    if (
        business
        .owner_involvement_hours_per_week
        is None
    ):
        missing.append(
            "owner_involvement_hours_per_week"
        )

    if business.transition_training_days is None:
        missing.append(
            "transition_training_days"
        )

    if business.deal_preference is None:
        missing.append(
            "deal_preference"
        )

    return ReadinessResult(
        ready=not missing,
        missing_fields=tuple(missing),
    )