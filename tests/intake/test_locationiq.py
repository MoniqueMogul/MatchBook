import io
import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from app.intake import locationiq


@pytest.fixture(autouse=True)
def isolated_provider(monkeypatch):
    monkeypatch.setattr(locationiq, "load_dotenv", lambda: None)
    monkeypatch.setenv("LOCATIONIQ_API_KEY", "test-placeholder")
    def unexpected_request(*args, **kwargs):
        pytest.fail("Unexpected network request")
    monkeypatch.setattr(locationiq, "urlopen", unexpected_request)


def provider_row():
    return {
        "place_id": "123", "display_name": "Calgary, Alberta, Canada",
        "lat": "51.05", "lon": "-114.07",
        "address": {"city": "Calgary", "county": "Calgary Region",
                    "state": "Alberta", "country": "Canada", "country_code": "ca"},
    }


def test_normalizes_response_and_request(monkeypatch):
    def request(url, timeout):
        parsed = urlsplit(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "api.locationiq.com"
        assert parsed.path == "/v1/autocomplete"
        params = parse_qs(parsed.query)
        assert params["q"] == ["Calgary & area"]
        assert params["limit"] == ["3"]
        assert params["layers"] == ["city,county,state,country"]
        assert params["normalizecity"] == ["1"]
        assert params["dedupe"] == ["1"]
        assert params["accept-language"] == ["en"]
        assert timeout == 5
        return io.BytesIO(json.dumps([provider_row()]).encode())
    monkeypatch.setattr(locationiq, "urlopen", request)
    result = locationiq.autocomplete_locations("Calgary & area", 3)
    assert [item.model_dump() for item in result] == [{
        "provider": "locationiq", "place_id": "123",
        "display_name": "Calgary, Alberta, Canada",
        "latitude": 51.05, "longitude": -114.07, "city": "Calgary",
        "county": "Calgary Region", "state": "Alberta", "country": "Canada",
        "country_code": "CA",
    }]


def test_missing_key(monkeypatch):
    monkeypatch.delenv("LOCATIONIQ_API_KEY", raising=False)
    with pytest.raises(locationiq.LocationAutocompleteConfigurationError):
        locationiq.autocomplete_locations("Calgary")


@pytest.mark.parametrize("error", [
    URLError("offline"), TimeoutError(),
    HTTPError("https://example.invalid", 429, "rate limited", {}, None),
])
def test_provider_failure(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(locationiq, "urlopen", fail)
    with pytest.raises(locationiq.LocationAutocompleteProviderError):
        locationiq.autocomplete_locations("Calgary")


@pytest.mark.parametrize("body", [b"not json", b'{"error":"unavailable"}', b"null", b"\xff"])
def test_invalid_response(monkeypatch, body):
    monkeypatch.setattr(locationiq, "urlopen", lambda *a, **k: io.BytesIO(body))
    with pytest.raises(locationiq.LocationAutocompleteProviderError):
        locationiq.autocomplete_locations("Calgary")


def test_skips_malformed_rows(monkeypatch):
    rows = [None, [], {}, {**provider_row(), "lat": "NaN"},
            {**provider_row(), "lon": 181}, {**provider_row(), "address": None},
            {**provider_row(), "place_id": {}},
            {**provider_row(), "display_name": " "}, provider_row()]
    monkeypatch.setattr(locationiq, "urlopen", lambda *a, **k: io.BytesIO(json.dumps(rows).encode()))
    assert len(locationiq.autocomplete_locations("Calgary")) == 1


@pytest.mark.parametrize("field", ["town", "municipality", "village", "locality"])
def test_city_fallback(monkeypatch, field):
    row = provider_row()
    row["address"] = {field: "Calgary"}
    monkeypatch.setattr(locationiq, "urlopen", lambda *a, **k: io.BytesIO(json.dumps([row]).encode()))
    assert locationiq.autocomplete_locations("Calgary")[0].city == "Calgary"
