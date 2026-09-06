from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(
    app
)


# ============================================================
# APPLICATION HEALTH
# ============================================================


def test_main_health():
    response = client.get(
        "/health"
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()
        == {
            "status": "healthy",
            "service": "matchbook-api",
        }
    )


# ============================================================
# MATCHING ROUTER REGISTRATION
# ============================================================


def test_matching_router_is_registered():
    response = client.get(
        "/api/matches/health"
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()
        == {
            "status": "healthy",
            "service": "matching",
        }
    )


# ============================================================
# DATABASE HEALTH - SUCCESS
# ============================================================


@patch(
    "app.main.check_database_connection",
    return_value=True,
)
def test_database_health_success(
    mock_database_check,
):
    response = client.get(
        "/health/database"
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()
        == {
            "status": "healthy",
            "service": "database",
        }
    )

    mock_database_check.assert_called_once_with()


# ============================================================
# DATABASE HEALTH - FAILURE
# ============================================================


@patch(
    "app.main.check_database_connection",
    return_value=False,
)
def test_database_health_unavailable(
    mock_database_check,
):
    response = client.get(
        "/health/database"
    )

    assert (
        response.status_code
        == 503
    )

    assert (
        response.json()
        == {
            "detail": "Database unavailable"
        }
    )

    mock_database_check.assert_called_once_with()