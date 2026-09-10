from decimal import Decimal

import pytest

from pydantic import ValidationError

from app.intake.schemas.buyer_preferences import (
    BuyerPreferencesUpsert,
)


def test_free_text_target_location_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BuyerPreferencesUpsert(target_locations={"state": "Texas"})


@pytest.mark.parametrize("changes", [
    {"provider": "other"}, {"place_id": " "}, {"place_id": "x" * 101},
    {"display_name": ""}, {"display_name": "x" * 501},
    {"latitude": 91}, {"longitude": -181}, {"latitude": float("nan")},
    {"city": "x" * 151}, {"county": "x" * 151},
    {"state": "x" * 151}, {"country": "x" * 151},
    {"country_code": "USA"}, {"country_code": "U"}, {"unexpected": True},
])
def test_invalid_selected_location_is_rejected(changes) -> None:
    selected = {
        "provider": "locationiq", "place_id": "123", "display_name": "Canada",
        "latitude": 56.0, "longitude": -106.0,
    }
    with pytest.raises(ValidationError):
        BuyerPreferencesUpsert(target_locations={**selected, **changes})


def test_selected_location_without_address_counts_as_present() -> None:
    preferences = BuyerPreferencesUpsert(target_locations={
        "provider": "locationiq", "place_id": "123", "display_name": "Canada",
        "latitude": 56.0, "longitude": -106.0, "country_code": "ca",
    })
    assert preferences.target_locations.has_any_value()
    assert preferences.target_locations.country_code == "CA"


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


def test_arr_preferences_are_accepted() -> None:

    preferences = BuyerPreferencesUpsert(
        minimum_required_arr=100000,
        preferred_arr=200000,
    )

    assert (
        preferences.minimum_required_arr
        == Decimal("100000")
    )

    assert (
        preferences.preferred_arr
        == Decimal("200000")
    )


def test_preferred_arr_cannot_be_below_minimum() -> None:

    with pytest.raises(ValidationError):

        BuyerPreferencesUpsert(
            minimum_required_arr=200000,
            preferred_arr=100000,
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
