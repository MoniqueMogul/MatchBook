"""Server-side LocationIQ autocomplete adapter."""

import json
import os
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv
from pydantic import ValidationError

from app.intake.schemas.common import TargetLocation


class LocationAutocompleteError(Exception):
    """Base autocomplete failure."""


class LocationAutocompleteConfigurationError(LocationAutocompleteError):
    """LocationIQ credentials are missing."""


class LocationAutocompleteProviderError(LocationAutocompleteError):
    """LocationIQ could not supply a usable response."""


def autocomplete_locations(q: str, limit: int = 8) -> list[TargetLocation]:
    load_dotenv()
    key = os.getenv("LOCATIONIQ_API_KEY", "").strip()
    if not key:
        raise LocationAutocompleteConfigurationError(
            "Location autocomplete is not configured."
        )

    params = urlencode({
        "key": key,
        "q": q,
        "limit": limit,
        "layers": "city,county,state,country",
        "normalizecity": 1,
        "dedupe": 1,
        "accept-language": "en",
    })
    try:
        with urlopen(
            "https://api.locationiq.com/v1/autocomplete?" + params,
            timeout=5,
        ) as response:
            rows = json.load(response)
    except (URLError, OSError, HTTPException, ValueError):
        # Provider exceptions can include the credential-bearing URL.
        raise LocationAutocompleteProviderError(
            "Location autocomplete provider is unavailable."
        ) from None

    if not isinstance(rows, list):
        raise LocationAutocompleteProviderError(
            "Location autocomplete provider is unavailable."
        )

    locations = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        address = row.get("address", {})
        if not isinstance(address, dict):
            continue
        place_id = row.get("place_id")
        if isinstance(place_id, bool) or not isinstance(place_id, (str, int)):
            continue
        city = next((
            address[field] for field in
            ("city", "town", "municipality", "village", "locality")
            if isinstance(address.get(field), str) and address[field].strip()
        ), None)
        try:
            locations.append(TargetLocation(
                provider="locationiq",
                place_id=str(place_id),
                display_name=row.get("display_name"),
                latitude=row.get("lat"),
                longitude=row.get("lon"),
                city=city,
                county=address.get("county"),
                state=address.get("state"),
                country=address.get("country"),
                country_code=address.get("country_code"),
            ))
        except ValidationError:
            continue
    return locations
