from unittest.mock import patch

from fastapi.testclient import (
    TestClient,
)

from app.main import app


client = TestClient(
    app
)


def test_application_health():
    response = client.get(
        "/health"
    )

    assert (
        response.status_code
        == 200
    )

    assert response.json() == {
        "status": "healthy",
        "service": "matchbook-api",
    }


def test_health_returns_request_id():
    response = client.get(
        "/health"
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        "X-Request-ID"
        in response.headers
    )


def test_existing_request_id_is_preserved():
    request_id = (
        "monitoring-test-request"
    )

    response = client.get(
        "/health",
        headers={
            "X-Request-ID": (
                request_id
            )
        },
    )

    assert (
        response.headers[
            "X-Request-ID"
        ]
        == request_id
    )


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

    assert response.json() == {
        "status": "healthy",
        "service": "database",
    }

    mock_database_check.assert_called_once_with()


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

    assert response.json() == {
        "detail": (
            "Database unavailable"
        )
    }

    mock_database_check.assert_called_once_with()