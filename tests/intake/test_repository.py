from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.db_model import (
    Business,
    BuyerProfile,
    OutboxEvent,
    SellerProfile,
    User,
)
from app.db.db_enum import EventType, OutboxStatus
from app.events.payload_schema import (
    BusinessCreatedPayload,
    BuyerCreatedPayload,
)
from app.intake.repository import (
    IntakeRepositoryError,
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

    buyer_id = uuid4()
    event_id = uuid4()

    def assign_ids() -> None:
        added = [
            call.args[0]
            for call in session.add.call_args_list
        ]
        if len(added) == 1:
            added[0].id = buyer_id
        else:
            added[1].id = event_id

    session.flush.side_effect = assign_ids

    profile, event = repository.create_buyer_profile(
        user_id,
        BuyerProfileCreate(
            buyer_type="first_time_owner",
            current_industry="HVAC",
        ),
    )

    created = session.add.call_args_list[0].args[0]

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

    assert event is session.add.call_args_list[1].args[0]
    assert isinstance(event, OutboxEvent)
    assert event.event_type == EventType.BUYER_CREATED
    assert event.entity_type == "buyer"
    assert event.entity_id == buyer_id
    assert event.idempotency_key == f"buyer_created:{buyer_id}"
    assert event.payload == {
        "buyer_id": str(buyer_id),
        "user_id": str(user_id),
    }
    method_names = [
        method_call[0]
        for method_call in session.method_calls
    ]
    assert method_names.count("commit") == 1
    assert method_names.index("commit") > max(
        index
        for index, name in enumerate(method_names)
        if name == "add"
    )
    assert session.refresh.call_count == 2


def test_create_buyer_profile_rolls_back_when_outbox_fails() -> None:

    user_id = uuid4()
    session = MagicMock(spec=Session)
    session.scalar.side_effect = [User(id=user_id), None]
    repository = IntakeRepository(session)

    with patch(
        "app.intake.repository.OutboxRepository.create_event",
        side_effect=RuntimeError("outbox unavailable"),
    ):
        try:
            repository.create_buyer_profile(
                user_id,
                BuyerProfileCreate(
                    buyer_type="first_time_owner"
                ),
            )
        except IntakeRepositoryError:
            pass
        else:
            raise AssertionError("Expected IntakeRepositoryError")

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_upsert_buyer_preferences_serializes_target_locations_as_list() -> None:

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
            target_locations=[{
                "provider": "locationiq",
                "place_id": "test-texas",
                "display_name": "Texas, United States",
                "latitude": 31.0,
                "longitude": -100.0,
                "city": None,
                "county": None,
                "state": "Texas",
                "country": "United States",
                "country_code": "US",
            }],
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
        == [{
            "provider": "locationiq",
            "place_id": "test-texas",
            "display_name": "Texas, United States",
            "latitude": 31.0,
            "longitude": -100.0,
            "city": None,
            "county": None,
            "state": "Texas",
            "country": "United States",
            "country_code": "US",
        }]
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

    business_id = uuid4()
    event_id = uuid4()

    def assign_ids() -> None:
        added = [
            call.args[0]
            for call in session.add.call_args_list
        ]
        if len(added) == 1:
            added[0].id = business_id
        else:
            added[1].id = event_id

    session.flush.side_effect = assign_ids

    (
        created,
        was_created,
        event,
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

    added = session.add.call_args_list[0].args[0]

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

    assert event is session.add.call_args_list[1].args[0]
    assert event.event_type == EventType.BUSINESS_CREATED
    assert event.entity_type == "business"
    assert event.entity_id == business_id
    assert event.idempotency_key == f"business_created:{business_id}"
    assert event.payload == {
        "business_id": str(business_id),
        "seller_id": str(seller_id),
        "seller_user_id": str(seller_user_id),
    }
    method_names = [
        method_call[0]
        for method_call in session.method_calls
    ]
    assert method_names.count("commit") == 1
    assert method_names.index("commit") > max(
        index
        for index, name in enumerate(method_names)
        if name == "add"
    )
    assert session.refresh.call_count == 2

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
        event,
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
    assert event is None

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

    def assign_race_ids() -> None:
        added = [
            call.args[0]
            for call in session.add.call_args_list
        ]
        if len(added) == 1:
            added[0].id = uuid4()
        else:
            added[1].id = uuid4()

    session.flush.side_effect = assign_race_ids

    (
        result,
        was_created,
        event,
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
    assert event is None

    session.rollback.assert_called_once()
    session.refresh.assert_not_called()


def test_create_business_rolls_back_when_outbox_fails() -> None:

    seller_user_id = uuid4()
    seller = SellerProfile(
        id=uuid4(),
        user_id=seller_user_id,
    )
    session = MagicMock(spec=Session)
    session.scalar.side_effect = [seller, None]
    repository = IntakeRepository(session)

    with patch(
        "app.intake.repository.OutboxRepository.create_event",
        side_effect=RuntimeError("outbox unavailable"),
    ):
        try:
            repository.create_business(
                seller_user_id,
                BusinessCreate(
                    business_type="Service",
                    industry="HVAC",
                    city="Austin",
                    state="Texas",
                ),
                "outbox-failure",
            )
        except IntakeRepositoryError:
            pass
        else:
            raise AssertionError("Expected IntakeRepositoryError")

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_outbox_events_default_to_pending() -> None:

    assert (
        OutboxEvent.__table__.c.status.default.arg
        == OutboxStatus.PENDING
    )


def test_creation_payload_schemas_require_uuids_and_serialize_json() -> None:

    buyer_id = uuid4()
    user_id = uuid4()
    business_id = uuid4()
    seller_id = uuid4()

    buyer_payload = BuyerCreatedPayload(
        buyer_id=buyer_id,
        user_id=user_id,
    )
    business_payload = BusinessCreatedPayload(
        business_id=business_id,
        seller_id=seller_id,
        seller_user_id=user_id,
    )

    assert buyer_payload.model_dump(mode="json") == {
        "buyer_id": str(buyer_id),
        "user_id": str(user_id),
    }
    assert business_payload.model_dump(mode="json") == {
        "business_id": str(business_id),
        "seller_id": str(seller_id),
        "seller_user_id": str(user_id),
    }

    with pytest.raises(ValidationError):
        BuyerCreatedPayload(
            buyer_id="not-a-uuid",
            user_id=user_id,
        )

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
