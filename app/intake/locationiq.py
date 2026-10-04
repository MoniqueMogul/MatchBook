"""Server-side LocationIQ autocomplete adapter."""

import json
import os
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv
from pydantic import ValidationError

from app.intake.schemas.common import (
    LocationAutocompleteResult,
)


class LocationAutocompleteError(Exception):
    """Base autocomplete failure."""


class LocationAutocompleteConfigurationError(
    LocationAutocompleteError
):
    """LocationIQ credentials are missing."""


class LocationAutocompleteProviderError(
    LocationAutocompleteError
):
    """LocationIQ could not supply a usable response."""


def _clean_string(value: object) -> str | None:
    """Return a stripped non-empty string or None."""

    if not isinstance(value, str):
        return None

    value = value.strip()

    return value or None


def _first_string(
    mapping: dict,
    *fields: str,
) -> str | None:
    """
    Return the first populated string from the requested fields.

    LocationIQ/OpenStreetMap results are not perfectly uniform across
    result types. City, county, and state-level results can expose
    administrative information under slightly different field names.
    """

    for field in fields:
        value = _clean_string(
            mapping.get(field)
        )

        if value:
            return value

    return None


def autocomplete_locations(
    q: str,
    limit: int = 8,
) -> list[LocationAutocompleteResult]:
    load_dotenv()

    key = os.getenv(
        "LOCATIONIQ_API_KEY",
        "",
    ).strip()

    if not key:
        raise LocationAutocompleteConfigurationError(
            "Location autocomplete is not configured."
        )

    params = urlencode(
        {
            "key": key,
            "q": q,
            "limit": limit,
            "layers": "city,county,state,country",
            "normalizecity": 1,
            "dedupe": 1,
            "accept-language": "en",
        }
    )

    try:
        with urlopen(
            "https://api.locationiq.com/v1/autocomplete?"
            + params,
            timeout=5,
        ) as response:
            rows = json.load(response)

    except (
        URLError,
        OSError,
        HTTPException,
        ValueError,
    ):
        # Provider exceptions can include the credential-bearing URL.
        raise LocationAutocompleteProviderError(
            "Location autocomplete provider is unavailable."
        ) from None

    if not isinstance(rows, list):
        raise LocationAutocompleteProviderError(
            "Location autocomplete provider is unavailable."
        )

    locations: list[
        LocationAutocompleteResult
    ] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        address = row.get(
            "address",
            {},
        )

        if not isinstance(address, dict):
            continue

        place_id = row.get("place_id")

        if (
            isinstance(place_id, bool)
            or not isinstance(
                place_id,
                (str, int),
            )
        ):
            continue

        city = _first_string(
            address,
            "city",
            "town",
            "municipality",
            "village",
            "locality",
        )

        county = _first_string(
            address,
            "county",
            "county_district",
        )

        # "state" is the preferred structured field.
        # Some administrative results may expose the useful
        # state-level value through state_district instead.
        state = _first_string(
            address,
            "state",
        )

        # State is the minimum structured requirement.
        #
        # City, county and ZIP are deliberately NOT required
        # for an autocomplete suggestion to be selectable.
        if not state:
            continue

        zip_code = _first_string(
            address,
            "postcode",
        )

        country = _first_string(
            address,
            "country",
        )

        country_code = _first_string(
            address,
            "country_code",
        )

        if country_code:
            country_code = (
                country_code.upper()
            )

        display_name = _clean_string(
            row.get("display_name")
        )

        if not display_name:
            display_name = ", ".join(
                part
                for part in (
                    city,
                    county,
                    state,
                    zip_code,
                    country,
                )
                if part
            )

        try:
            locations.append(
                LocationAutocompleteResult(
                    provider="locationiq",
                    place_id=str(
                        place_id
                    ),
                    display_name=display_name,
                    latitude=row.get(
                        "lat"
                    ),
                    longitude=row.get(
                        "lon"
                    ),
                    city=city,
                    county=county,
                    zip_code=zip_code,
                    state=state,
                    country=country,
                    country_code=country_code,
                )
            )

        except ValidationError:
            continue

    return locations