"""No longer used in the current financial verification flow.

Kept as a stub for a future external tax/records provider.
"""

import os
from typing import Any

import httpx

TAX_PROVIDER_BASE_URL = os.environ.get("TAX_PROVIDER_BASE_URL", "")
TAX_PROVIDER_API_KEY = os.environ.get("TAX_PROVIDER_API_KEY", "")


async def get_business_financial_records(ein: str) -> dict[str, Any]:
    if not TAX_PROVIDER_BASE_URL:
        raise NotImplementedError(
            "Tax provider not yet selected/configured — see TODO in this file."
        )

    async with httpx.AsyncClient(base_url=TAX_PROVIDER_BASE_URL, timeout=20.0) as client:
        response = await client.get(
            f"/businesses/{ein}/financials",
            headers={"Authorization": f"Bearer {TAX_PROVIDER_API_KEY}"},
        )
        response.raise_for_status()
        raw = response.json()

    return _normalize(raw)


async def verify_business_existence(ein: str, legal_name: str) -> dict[str, Any]:
    raise NotImplementedError("Depends on provider selection — see TODO above.")


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "revenue": raw.get("revenue"),
        "sde": raw.get("sde"),
        "tax_year": raw.get("tax_year"),
        "reference_id": raw.get("id", ""),
        "raw": raw,
    }