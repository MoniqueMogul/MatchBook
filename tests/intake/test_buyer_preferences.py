from decimal import Decimal

import pytest

from pydantic import ValidationError

from app.intake.schemas.buyer_preferences import (
    BuyerPreferencesUpsert,
)


def test_preferences_can_be_partial_during_draft() -> None:

    preferences = BuyerPreferencesUpsert(
        maximum_purchase_price=500000
    )

    assert (
        preferences.maximum_purchase_price
        == Decimal("500000")
    )

    assert preferences.minimum_required_sde is None


def test_industries_are_trimmed_deduplicated_and_blanks_removed() -> None:

    preferences = BuyerPreferencesUpsert(
        target_industries=[
            " HVAC ",
            "Landscaping",
            "hvac",
            "",
        ],
    )

    assert preferences.target_industries == [
        "HVAC",
        "Landscaping",
    ]


def test_preferred_sde_cannot_be_below_minimum() -> None:

    with pytest.raises(ValidationError):

        BuyerPreferencesUpsert(
            minimum_required_sde=200000,
            preferred_sde=100000,
        )


def test_aar_preferences_are_accepted() -> None:

    preferences = BuyerPreferencesUpsert(
        minimum_required_aar=100000,
        preferred_aar=200000,
    )

    assert (
        preferences.minimum_required_aar
        == Decimal("100000")
    )

    assert (
        preferences.preferred_aar
        == Decimal("200000")
    )


def test_preferred_aar_cannot_be_below_minimum() -> None:

    with pytest.raises(ValidationError):

        BuyerPreferencesUpsert(
            minimum_required_aar=200000,
            preferred_aar=100000,
        )


def test_negative_training_days_are_rejected() -> None:

    with pytest.raises(ValidationError):

        BuyerPreferencesUpsert(
            required_transition_training_days=-1
        )


def test_unknown_fields_are_rejected() -> None:

    with pytest.raises(ValidationError):

        BuyerPreferencesUpsert(
            maximum_purchase_price=500000,
            made_up_field=True,
        )


def test_invalid_deal_preference_is_rejected() -> None:

    with pytest.raises(ValidationError):

        BuyerPreferencesUpsert(
            deal_preference="crypto"
        )