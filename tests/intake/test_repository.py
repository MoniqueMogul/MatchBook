from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.db_model import (
    Business,
    BuyerProfile,
    User,
)
from app.intake.repository import (
    IntakeRepository,
)
from app.intake.schemas.business import (
    BusinessUpdate,
)
from app.intake.schemas.buyer import (
    BuyerProfileCreate,
)
from app.intake.schemas.buyer_preferences import (
    BuyerPreferencesUpsert,
)


def test_create_buyer_profile_persists_validated_payload() -> None:

    user_id = uuid4()

    session = MagicMock(
        spec=Session
    )

    session.scalar.side_effect = [
        User(
            id=user_id,
            first_name="Test",
            last_name="User",
        ),
        None,
    ]

    repository = IntakeRepository(
        session
    )

    repository.create_buyer_profile(
        user_id,
        BuyerProfileCreate(
            buyer_type="first_time_owner",
            current_industry="HVAC",
        ),
    )

    created = (
        session.add.call_args.args[0]
    )

    assert isinstance(
        created,
        BuyerProfile,
    )

    assert created.user_id == user_id

    assert (
        created.buyer_type
        == "first_time_owner"
    )

    assert (
        created.current_industry
        == "HVAC"
    )

    session.commit.assert_called_once()

    session.refresh.assert_called_once_with(
        created
    )


def test_upsert_buyer_preferences_serializes_target_location() -> None:

    user_id = uuid4()
    buyer_id = uuid4()

    profile = BuyerProfile(
        id=buyer_id,
        user_id=user_id,
        buyer_type="first_time_owner",
    )

    session = MagicMock(
        spec=Session
    )

    session.scalar.side_effect = [
        profile,
        None,
    ]

    repository = IntakeRepository(
        session
    )

    repository.upsert_buyer_preferences(
        user_id,
        BuyerPreferencesUpsert(
            target_locations={
                "state": "Texas",
            },
            minimum_required_arr=150000,
        ),
    )

    created = (
        session.add.call_args.args[0]
    )

    assert (
        created.buyer_id
        == buyer_id
    )

    assert (
        created.target_locations
        == {
            "state": "Texas",
        }
    )

    assert (
        created.minimum_required_arr
        == Decimal("150000")
    )


def test_update_business_changes_only_supplied_fields() -> None:

    seller_user_id = uuid4()
    business_id = uuid4()

    business = Business(
        id=business_id,
        seller_id=uuid4(),
        business_type="Service",
        industry="HVAC",
        city="Austin",
        state="Texas",
        asking_price=Decimal(
            "500000"
        ),
    )

    session = MagicMock(
        spec=Session
    )

    session.scalar.return_value = (
        business
    )

    repository = IntakeRepository(
        session
    )

    updated = repository.update_business(
        seller_user_id,
        business_id,
        BusinessUpdate(
            asking_price=550000
        ),
    )

    assert (
        updated.asking_price
        == Decimal("550000")
    )

    assert (
        updated.industry
        == "HVAC"
    )

    assert (
        updated.city
        == "Austin"
    )

    session.commit.assert_called_once()

    session.refresh.assert_called_once_with(
        business
    )