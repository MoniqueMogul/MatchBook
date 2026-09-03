from app.intake.schemas.business import (
    BusinessCreate,
)

from app.intake.schemas.buyer_preferences import (
    BuyerPreferencesUpsert,
)

from app.intake.validation.readiness import (
    business_readiness,
    buyer_preferences_readiness,
)


def test_complete_buyer_preferences_are_matching_ready() -> None:

    preferences = BuyerPreferencesUpsert(
        target_industries=["HVAC"],
        target_locations={
            "state": "Texas"
        },
        maximum_purchase_price=500000,
        minimum_required_sde=100000,
        preferred_sde=200000,
        preferred_owner_hours_per_week=20,
        required_transition_training_days=30,
        deal_preference="financing",
    )

    result = buyer_preferences_readiness(
        preferences
    )

    assert result.ready is True
    assert result.missing_fields == ()


def test_incomplete_buyer_preferences_report_missing_fields() -> None:

    preferences = BuyerPreferencesUpsert(
        maximum_purchase_price=500000
    )

    result = buyer_preferences_readiness(
        preferences
    )

    assert result.ready is False

    assert (
        "target_industries"
        in result.missing_fields
    )

    assert (
        "minimum_required_sde"
        in result.missing_fields
    )


def test_complete_business_is_matching_ready() -> None:

    business = BusinessCreate(
        business_type="Home Services",
        industry="HVAC",
        city="Dallas",
        state="Texas",
        asking_price=500000,
        sde=150000,
        owner_involvement_hours_per_week=20,
        transition_training_days=30,
        deal_preference="financing",
    )

    result = business_readiness(
        business
    )

    assert result.ready is True


def test_draft_business_is_not_matching_ready() -> None:

    business = BusinessCreate(
        business_type="Home Services",
        industry="HVAC",
        city="Dallas",
        state="Texas",
    )

    result = business_readiness(
        business
    )

    assert result.ready is False

    assert (
        "asking_price"
        in result.missing_fields
    )