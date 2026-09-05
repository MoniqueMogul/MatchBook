from fastapi.testclient import TestClient

from app.main import app


client = TestClient(
    app
)


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