from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.intake.dependencies import (
    get_intake_repository,
)
from app.intake.repository import (
    IntakeConflictError,
)
from app.intake.routes import router


def build_client(
    repository: object,
) -> TestClient:

    app = FastAPI()

    app.include_router(
        router
    )

    app.dependency_overrides[
        get_intake_repository
    ] = lambda: repository

    return TestClient(
        app
    )


def test_missing_buyer_profile_returns_404() -> None:

    repository = MagicMock()

    repository.get_buyer_profile_by_user_id.return_value = None

    client = build_client(
        repository
    )

    response = client.get(
        (
            f"/intake/buyers/"
            f"{uuid4()}/profile"
        )
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


def test_duplicate_buyer_profile_returns_409() -> None:

    repository = MagicMock()

    repository.create_buyer_profile.side_effect = (
        IntakeConflictError(
            "Buyer profile already exists "
            "for this user."
        )
    )

    client = build_client(
        repository
    )

    response = client.post(
        (
            f"/intake/buyers/"
            f"{uuid4()}/profile"
        ),
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


def test_buyer_readiness_returns_missing_fields() -> None:

    repository = MagicMock()

    repository.get_buyer_preferences_by_user_id.return_value = (
        SimpleNamespace(
            target_industries=[
                "HVAC"
            ],
            target_locations={
                "state": "Texas"
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

    client = build_client(
        repository
    )

    response = client.get(
        (
            f"/intake/buyers/"
            f"{uuid4()}/readiness"
        )
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