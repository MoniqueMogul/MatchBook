import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


fake_auth_module = ModuleType(
    "app.auth.auth"
)

fake_auth_module.supabase = MagicMock()

sys.modules.setdefault(
    "app.auth.auth",
    fake_auth_module,
)


from app.auth.dependencies import get_current_user_id
from app.intake.locationiq import (
    LocationAutocompleteConfigurationError,
    LocationAutocompleteProviderError,
)
from app.intake.routes import router
from app.intake.schemas.common import (
    LocationAutocompleteResult,
)


def build_client(
        _repository: object,
) -> tuple[TestClient, object]:

    authenticated_user_id = uuid4()

    app = FastAPI()

    app.include_router(
        router,
        dependencies=[
            Depends(get_current_user_id),
        ],
    )

    app.dependency_overrides[
        get_current_user_id
    ] = lambda: authenticated_user_id

    return (
        TestClient(app),
        authenticated_user_id,
    )

def test_authenticated_results_and_limit():
    selected = LocationAutocompleteResult(
        provider="locationiq", place_id="123", display_name="Calgary, Canada",
        latitude=51.05, longitude=-114.07, country_code="ca",
    )
    client, _ = build_client(MagicMock())
    with patch("app.intake.routes.autocomplete_locations", return_value=[selected]) as provider:
        response = client.get("/intake/locations/autocomplete", params={"q": "Calgary", "limit": 3})
    assert response.status_code == 200
    assert response.json() == [selected.model_dump()]
    provider.assert_called_once_with("Calgary", 3)


def test_default_limit():
    client, _ = build_client(MagicMock())
    with patch("app.intake.routes.autocomplete_locations", return_value=[]) as provider:
        assert client.get("/intake/locations/autocomplete?q=Calgary").status_code == 200
    provider.assert_called_once_with("Calgary", 8)


@pytest.mark.parametrize("params", [
    {}, {"q": "ab"}, {"q": "x" * 201},
    {"q": "Calgary", "limit": 0}, {"q": "Calgary", "limit": 21},
])
def test_invalid_query(params):
    client, _ = build_client(MagicMock())
    with patch("app.intake.routes.autocomplete_locations") as provider:
        assert client.get("/intake/locations/autocomplete", params=params).status_code == 422
    provider.assert_not_called()


@pytest.mark.parametrize("error,code,detail", [
    (LocationAutocompleteProviderError, 502, "Location autocomplete provider is unavailable."),
    (LocationAutocompleteConfigurationError, 503, "Location autocomplete is not configured."),
])
def test_error_mapping(error, code, detail):
    client, _ = build_client(MagicMock())
    with patch("app.intake.routes.autocomplete_locations", side_effect=error("private provider detail")):
        response = client.get("/intake/locations/autocomplete?q=Calgary")
    assert response.status_code == code
    assert response.json() == {"detail": detail}


def test_requires_authentication():
    client, _ = build_client(MagicMock())
    del client.app.dependency_overrides[get_current_user_id]
    with patch("app.intake.routes.autocomplete_locations") as provider:
        assert client.get("/intake/locations/autocomplete?q=Calgary").status_code in (401, 403)
    provider.assert_not_called()
