import sys
from datetime import datetime, timezone
from types import (
    ModuleType,
    SimpleNamespace,
)
from unittest.mock import (
    MagicMock,
    patch,
)
from uuid import uuid4


# ------------------------------------------------------------
# Stub the shared Supabase client before importing
# app.auth.dependencies.
#
# Intake route tests verify that the routes depend on
# get_current_user_id. Tim's auth implementation itself
# should be tested separately by the auth module.
# ------------------------------------------------------------

fake_auth_module = ModuleType(
    "app.auth.auth"
)

fake_auth_module.supabase = MagicMock()

sys.modules.setdefault(
    "app.auth.auth",
    fake_auth_module,
)


from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import (
    get_current_user_id,
)
from app.intake.dependencies import (
    get_intake_repository,
)
from app.intake.repository import (
    IntakeConflictError,
    IntakeRepositoryError,
)
from app.intake.routes import (
    _enqueue_outbox_event,
    router,
)


def build_client(
    repository: object,
    user_id=None,
) -> tuple[TestClient, object]:

    authenticated_user_id = (
        user_id or uuid4()
    )

    app = FastAPI()

    app.include_router(
        router
    )

    app.dependency_overrides[
        get_intake_repository
    ] = lambda: repository

    app.dependency_overrides[
        get_current_user_id
    ] = lambda: authenticated_user_id

    return (
        TestClient(app),
        authenticated_user_id,
    )


def build_buyer_profile_result(
    *,
    user_id,
    buyer_id,
) -> SimpleNamespace:

    now = datetime.now(
        timezone.utc
    )

    return SimpleNamespace(
        id=buyer_id,
        user_id=user_id,
        buyer_type="first_time_owner",
        current_industry="HVAC",
        current_position=None,
        business_experience_years=None,
        relevant_experience=None,
        available_hours_per_week=None,
        city=None,
        county=None,
        state=None,
        zip_code=None,
        verification_status="unverified",
        created_at=now,
        updated_at=now,
    )


def build_business_result(
    *,
    seller_id,
    business_id,
) -> SimpleNamespace:

    now = datetime.now(
        timezone.utc
    )

    return SimpleNamespace(
        id=business_id,
        seller_id=seller_id,
        legal_name=None,
        dba=None,
        business_type="Service",
        industry="HVAC",
        city="Austin",
        county=None,
        state="Texas",
        zip_code=None,
        years_in_operation=None,
        number_of_locations=None,
        number_of_routes=None,
        arr=None,
        customer_concentration=None,
        asking_price=None,
        sde=None,
        owner_involvement_hours_per_week=None,
        transition_training_days=None,
        deal_preference=None,
        preferred_sale_timeline=None,
        verification_status="unverified",
        status="draft",
        created_at=now,
        updated_at=now,
    )


def test_missing_buyer_profile_returns_404() -> None:

    repository = MagicMock()

    repository.get_buyer_profile_by_user_id.return_value = None

    client, user_id = build_client(
        repository
    )

    response = client.get(
        "/intake/buyers/profile"
    )

    assert (
        response.status_code
        == 404
    )

    assert (
        response.json()["detail"]
        == (
            "Buyer profile does not exist "
            "for this user."
        )
    )

    repository.get_buyer_profile_by_user_id.assert_called_once_with(
        user_id
    )


def test_duplicate_buyer_profile_returns_409() -> None:

    repository = MagicMock()

    repository.create_buyer_profile.side_effect = (
        IntakeConflictError(
            "Buyer profile already exists "
            "for this user."
        )
    )

    client, user_id = build_client(
        repository
    )

    with patch(
        "app.intake.routes._enqueue_outbox_event"
    ) as enqueue_mock:

        response = client.post(
            "/intake/buyers/profile",
            json={
                "buyer_type": (
                    "first_time_owner"
                ),
            },
        )

    assert (
        response.status_code
        == 409
    )

    assert (
        response.json()["detail"]
        == (
            "Buyer profile already exists "
            "for this user."
        )
    )

    call = (
        repository
        .create_buyer_profile
        .call_args
    )

    assert (
        call.args[0]
        == user_id
    )

    enqueue_mock.assert_not_called()


def test_create_buyer_profile_enqueues_persisted_outbox_event() -> None:

    repository = MagicMock()

    buyer_id = uuid4()

    client, user_id = build_client(
        repository
    )

    outbox_id = uuid4()
    repository.create_buyer_profile.return_value = (
        build_buyer_profile_result(
            user_id=user_id,
            buyer_id=buyer_id,
        ),
        SimpleNamespace(id=outbox_id),
    )

    with patch(
        "app.intake.routes._enqueue_outbox_event"
    ) as enqueue_mock:

        response = client.post(
            "/intake/buyers/profile",
            json={
                "buyer_type": (
                    "first_time_owner"
                ),
                "current_industry": "HVAC",
            },
        )

    assert (
        response.status_code
        == 201
    )

    repository.create_buyer_profile.assert_called_once()

    call = (
        repository
        .create_buyer_profile
        .call_args
    )

    assert (
        call.args[0]
        == user_id
    )

    enqueue_mock.assert_called_once_with(
        outbox_id
    )


def test_buyer_persistence_failure_does_not_enqueue() -> None:

    repository = MagicMock()
    repository.create_buyer_profile.side_effect = (
        IntakeRepositoryError("outbox failed")
    )
    client, _ = build_client(repository)

    with patch(
        "app.intake.routes._enqueue_outbox_event"
    ) as enqueue_mock:
        response = client.post(
            "/intake/buyers/profile",
            json={"buyer_type": "first_time_owner"},
        )

    assert response.status_code == 500
    enqueue_mock.assert_not_called()


def test_buyer_readiness_returns_missing_fields() -> None:

    repository = MagicMock()

    repository.get_buyer_preferences_by_user_id.return_value = (
        SimpleNamespace(
            target_industries=[
                "HVAC"
            ],
            target_locations={
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
            },
            maximum_purchase_price=500000,
            minimum_required_sde=100000,
            preferred_sde=200000,
            minimum_required_arr=None,
            preferred_arr=None,
            preferred_owner_hours_per_week=20,
            required_transition_training_days=30,
            deal_preference="financing",
            real_estate_preference=None,
            minimum_years_in_operation=None,
            accepts_customer_concentration_above_25_percent=False,
            preferred_acquisition_timeline=(
                "3-6 months"
            ),
        )
    )

    client, user_id = build_client(
        repository
    )

    response = client.get(
        "/intake/buyers/readiness"
    )

    assert (
        response.status_code
        == 200
    )

    assert response.json() == {
        "ready": False,
        "missing_fields": [
            "minimum_required_arr",
            "preferred_arr",
        ],
    }

    repository.get_buyer_preferences_by_user_id.assert_called_once_with(
        user_id
    )


def test_create_business_uses_auth_user_and_enqueues_outbox_event() -> None:

    repository = MagicMock()

    seller_id = uuid4()
    business_id = uuid4()

    business = build_business_result(
        seller_id=seller_id,
        business_id=business_id,
    )

    outbox_id = uuid4()
    repository.create_business.return_value = (
        business,
        True,
        SimpleNamespace(id=outbox_id),
    )

    client, user_id = build_client(
        repository
    )

    with patch(
        "app.intake.routes._enqueue_outbox_event"
    ) as enqueue_mock:

        response = client.post(
            "/intake/sellers/businesses",
            headers={
                "Idempotency-Key": (
                    "business-request-123"
                ),
            },
            json={
                "business_type": "Service",
                "industry": "HVAC",
                "city": "Austin",
                "state": "Texas",
            },
        )

    assert (
        response.status_code
        == 201
    )

    call = (
        repository
        .create_business
        .call_args
    )

    assert (
        call.args[0]
        == user_id
    )

    assert (
        call.args[2]
        == "business-request-123"
    )

    enqueue_mock.assert_called_once_with(
        outbox_id
    )


def test_idempotent_business_replay_does_not_publish_duplicate_event() -> None:

    repository = MagicMock()

    seller_id = uuid4()
    business_id = uuid4()

    business = build_business_result(
        seller_id=seller_id,
        business_id=business_id,
    )

    repository.create_business.return_value = (
        business,
        False,
        None,
    )

    client, _ = build_client(
        repository
    )

    with patch(
        "app.intake.routes._enqueue_outbox_event"
    ) as enqueue_mock:

        response = client.post(
            "/intake/sellers/businesses",
            headers={
                "Idempotency-Key": (
                    "same-request"
                ),
            },
            json={
                "business_type": "Service",
                "industry": "HVAC",
                "city": "Austin",
                "state": "Texas",
            },
        )

    assert (
        response.status_code
        == 201
    )

    enqueue_mock.assert_not_called()


def test_business_persistence_failure_does_not_enqueue() -> None:

    repository = MagicMock()
    repository.create_business.side_effect = (
        IntakeRepositoryError("outbox failed")
    )
    client, _ = build_client(repository)

    with patch(
        "app.intake.routes._enqueue_outbox_event"
    ) as enqueue_mock:
        response = client.post(
            "/intake/sellers/businesses",
            headers={"Idempotency-Key": "failed-request"},
            json={
                "business_type": "Service",
                "industry": "HVAC",
                "city": "Austin",
                "state": "Texas",
            },
        )

    assert response.status_code == 500
    enqueue_mock.assert_not_called()


def test_enqueue_outbox_event_passes_persisted_id_to_task() -> None:

    event_id = uuid4()
    task = MagicMock()
    fake_tasks_module = ModuleType("app.events.tasks")
    fake_tasks_module.send_outbox_event = task

    with patch.dict(
        sys.modules,
        {"app.events.tasks": fake_tasks_module},
    ):
        _enqueue_outbox_event(event_id)

    task.delay.assert_called_once_with(str(event_id))


def test_create_business_requires_idempotency_key() -> None:

    repository = MagicMock()

    client, _ = build_client(
        repository
    )

    response = client.post(
        "/intake/sellers/businesses",
        json={
            "business_type": "Service",
            "industry": "HVAC",
            "city": "Austin",
            "state": "Texas",
        },
    )

    assert (
        response.status_code
        == 422
    )

    repository.create_business.assert_not_called()
