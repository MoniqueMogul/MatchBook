from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.db_model import (
    Business,
    BuyerProfile,
    SellerProfile,
    User,
)
from app.intake.repository import (
    IntakeRepository,
)
from app.intake.schemas.business import (
    BusinessCreate,
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


def test_create_business_persists_idempotency_key() -> None:

    seller_user_id = uuid4()
    seller_id = uuid4()

    seller = SellerProfile(
        id=seller_id,
        user_id=seller_user_id,
    )

    session = MagicMock(
        spec=Session
    )

    session.scalar.side_effect = [
        seller,
        None,
    ]

    repository = IntakeRepository(
        session
    )

    (
        created,
        was_created,
    ) = repository.create_business(
        seller_user_id,
        BusinessCreate(
            business_type="Service",
            industry="HVAC",
            city="Austin",
            state="Texas",
        ),
        "create-business-123",
    )

    added = (
        session.add.call_args.args[0]
    )

    assert created is added
    assert was_created is True

    assert isinstance(
        added,
        Business,
    )

    assert (
        added.seller_id
        == seller_id
    )

    assert (
        added.idempotency_key
        == "create-business-123"
    )

    assert (
        added.industry
        == "HVAC"
    )

    session.commit.assert_called_once()

    session.refresh.assert_called_once_with(
        added
    )

def test_create_business_reuses_existing_idempotent_result() -> None:

    seller_user_id = uuid4()
    seller_id = uuid4()

    seller = SellerProfile(
        id=seller_id,
        user_id=seller_user_id,
    )

    existing = Business(
        id=uuid4(),
        seller_id=seller_id,
        idempotency_key="same-request",
        business_type="Service",
        industry="HVAC",
        city="Austin",
        state="Texas",
    )

    session = MagicMock(
        spec=Session
    )

    session.scalar.side_effect = [
        seller,
        existing,
    ]

    repository = IntakeRepository(
        session
    )

    (
        result,
        was_created,
    ) = repository.create_business(
        seller_user_id,
        BusinessCreate(
            business_type="Service",
            industry="HVAC",
            city="Austin",
            state="Texas",
        ),
        "same-request",
    )

    assert result is existing
    assert was_created is False

    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_create_business_recovers_from_idempotency_race() -> None:

    seller_user_id = uuid4()
    seller_id = uuid4()

    seller = SellerProfile(
        id=seller_id,
        user_id=seller_user_id,
    )

    existing = Business(
        id=uuid4(),
        seller_id=seller_id,
        idempotency_key="racing-request",
        business_type="Service",
        industry="HVAC",
        city="Austin",
        state="Texas",
    )

    session = MagicMock(
        spec=Session
    )

    # 1. seller lookup
    # 2. no idempotent business yet
    # 3. after failed INSERT, another request's
    #    business is now visible
    session.scalar.side_effect = [
        seller,
        None,
        existing,
    ]

    session.commit.side_effect = (
        IntegrityError(
            "INSERT",
            {},
            Exception("duplicate"),
        )
    )

    repository = IntakeRepository(
        session
    )

    (
        result,
        was_created,
    ) = repository.create_business(
        seller_user_id,
        BusinessCreate(
            business_type="Service",
            industry="HVAC",
            city="Austin",
            state="Texas",
        ),
        "racing-request",
    )

    assert result is existing
    assert was_created is False

    session.rollback.assert_called_once()
    session.refresh.assert_not_called()

def test_update_business_changes_only_supplied_fields() -> None:

    seller_user_id = uuid4()
    business_id = uuid4()

    business = Business(
        id=business_id,
        seller_id=uuid4(),
        idempotency_key="update-business",
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