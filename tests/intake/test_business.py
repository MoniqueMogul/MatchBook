from decimal import Decimal

import pytest

from pydantic import ValidationError

from app.intake.schemas.business import (
    BusinessCreate,
    BusinessUpdate,
)


def valid_business_data() -> dict:

    return {
        "business_type": "Home Services",
        "industry": "HVAC",
        "city": "Dallas",
        "state": "Texas",
    }


def test_valid_draft_business() -> None:

    business = BusinessCreate(
        **valid_business_data()
    )

    assert business.industry == "HVAC"
    assert business.asking_price is None


def test_required_business_string_cannot_be_blank() -> None:

    data = valid_business_data()

    data["industry"] = "   "

    with pytest.raises(ValidationError):

        BusinessCreate(**data)


def test_owner_hours_cannot_exceed_week() -> None:

    data = valid_business_data()

    data[
        "owner_involvement_hours_per_week"
    ] = 200

    with pytest.raises(ValidationError):

        BusinessCreate(**data)


def test_asking_price_must_be_positive_when_provided() -> None:

    data = valid_business_data()

    data["asking_price"] = -1

    with pytest.raises(ValidationError):

        BusinessCreate(**data)


def test_business_aar_is_accepted() -> None:

    data = valid_business_data()

    data["aar"] = 250000

    business = BusinessCreate(**data)

    assert business.aar == Decimal("250000")


def test_negative_business_aar_is_rejected() -> None:

    data = valid_business_data()

    data["aar"] = -1

    with pytest.raises(ValidationError):

        BusinessCreate(**data)


def test_customer_concentration_must_be_percentage() -> None:

    data = valid_business_data()

    data["customer_concentration"] = 101

    with pytest.raises(ValidationError):

        BusinessCreate(**data)


def test_business_update_can_be_partial() -> None:

    update = BusinessUpdate(
        asking_price=750000
    )

    assert update.asking_price is not None
    assert update.industry is None