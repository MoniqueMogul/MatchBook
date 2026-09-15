import pytest

from pydantic import ValidationError

from app.intake.schemas.buyer import (
    BuyerProfileCreate,
    BuyerProfileUpdate,
)


def test_valid_buyer_profile() -> None:

    profile = BuyerProfileCreate(
        buyer_type="first_time_owner",
        current_industry="  Healthcare  ",
        available_hours_per_week=20,
    )

    assert profile.current_industry == "Healthcare"
    assert profile.available_hours_per_week == 20


def test_buyer_type_must_be_known_enum_value() -> None:

    with pytest.raises(ValidationError):

        BuyerProfileCreate(
            buyer_type="random_type"
        )


def test_buyer_hours_cannot_exceed_week() -> None:

    with pytest.raises(ValidationError):

        BuyerProfileCreate(
            buyer_type="first_time_owner",
            available_hours_per_week=169,
        )


def test_update_can_be_partial() -> None:

    update = BuyerProfileUpdate(
        current_position="President"
    )

    assert update.current_position == "President"
    assert update.buyer_type is None