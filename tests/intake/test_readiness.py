from app.intake.schemas.business import BusinessCreate
from app.intake.schemas.buyer_preferences import BuyerPreferencesUpsert
from app.intake.validation.readiness import (
    business_readiness,
    buyer_preferences_readiness,
)


def test_complete_buyer_preferences_are_matching_ready() -> None:

    preferences = BuyerPreferencesUpsert(
        target_industries=["HVAC"],
        target_locations={
            "state": "Texas",
        },
        maximum_purchase_price=500000,
        minimum_required_sde=100000,
        preferred_sde=200000,
        minimum_required_arr=150000,
        preferred_arr=250000,
        preferred_owner_hours_per_week=20,
        required_transition_training_days=30,
        deal_preference="financing",
        accepts_customer_concentration_above_25_percent=False,
        preferred_sale_timeline="3-6 months",
    )

    result = buyer_preferences_readiness(preferences)

    assert result.ready is True
    assert result.missing_fields == ()


def test_incomplete_buyer_preferences_report_missing_fields() -> None:

    preferences = BuyerPreferencesUpsert(
        maximum_purchase_price=500000,
    )

    result = buyer_preferences_readiness(preferences)

    assert result.ready is False

    assert "target_industries" in result.missing_fields
    assert "target_locations" in result.missing_fields
    assert "minimum_required_sde" in result.missing_fields
    assert "preferred_sde" in result.missing_fields
    assert "minimum_required_arr" in result.missing_fields
    assert "preferred_arr" in result.missing_fields


def test_false_customer_concentration_preference_counts_as_answered() -> None:

    preferences = BuyerPreferencesUpsert(
        target_industries=["HVAC"],
        target_locations={
            "state": "Texas",
        },
        maximum_purchase_price=500000,
        minimum_required_sde=100000,
        preferred_sde=200000,
        minimum_required_arr=150000,
        preferred_arr=250000,
        preferred_owner_hours_per_week=20,
        required_transition_training_days=30,
        deal_preference="financing",
        accepts_customer_concentration_above_25_percent=False,
        preferred_sale_timeline="3-6 months",
    )

    result = buyer_preferences_readiness(preferences)

    assert result.ready is True


def test_new_matching_dimensions_are_required_for_buyer_readiness() -> None:

    preferences = BuyerPreferencesUpsert(
        target_industries=["HVAC"],
        target_locations={
            "state": "Texas",
        },
        maximum_purchase_price=500000,
        minimum_required_sde=100000,
        preferred_sde=200000,
        preferred_owner_hours_per_week=20,
        required_transition_training_days=30,
        deal_preference="financing",
    )

    result = buyer_preferences_readiness(preferences)

    assert result.ready is False

    assert "minimum_required_arr" in result.missing_fields
    assert "preferred_arr" in result.missing_fields

    assert (
        "accepts_customer_concentration_above_25_percent"
        in result.missing_fields
    )

    assert (
        "preferred_sale_timeline"
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
        arr=250000,
        customer_concentration=20,
        owner_involvement_hours_per_week=20,
        transition_training_days=30,
        deal_preference="financing",
        preferred_sale_timeline="3-6 months",
    )

    result = business_readiness(business)

    assert result.ready is True
    assert result.missing_fields == ()


def test_draft_business_is_not_matching_ready() -> None:

    business = BusinessCreate(
        business_type="Home Services",
        industry="HVAC",
        city="Dallas",
        state="Texas",
    )

    result = business_readiness(business)

    assert result.ready is False

    assert "asking_price" in result.missing_fields
    assert "sde" in result.missing_fields
    assert "arr" in result.missing_fields
    assert "customer_concentration" in result.missing_fields
    assert "owner_involvement_hours_per_week" in result.missing_fields
    assert "transition_training_days" in result.missing_fields
    assert "deal_preference" in result.missing_fields
    assert "preferred_sale_timeline" in result.missing_fields


def test_new_matching_dimensions_are_required_for_business_readiness() -> None:

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

    result = business_readiness(business)

    assert result.ready is False

    assert "arr" in result.missing_fields
    assert "customer_concentration" in result.missing_fields

    assert (
        "preferred_sale_timeline"
        in result.missing_fields
    )