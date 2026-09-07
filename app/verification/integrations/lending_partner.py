"""TODO: lending partner not yet selected — stub interface."""
import os
from typing import Any, Optional

import httpx

LENDING_PARTNER_BASE_URL = os.environ.get("LENDING_PARTNER_BASE_URL", "")
LENDING_PARTNER_API_KEY = os.environ.get("LENDING_PARTNER_API_KEY", "")


async def submit_financing_request(buyer_id: str, business_id: str, amount_requested: float, lender_name: Optional[str] = None) -> dict:
    if not LENDING_PARTNER_BASE_URL:
        raise NotImplementedError("Lending partner not yet selected/configured.")
    async with httpx.AsyncClient(base_url=LENDING_PARTNER_BASE_URL, timeout=20.0) as client:
        response = await client.post("/financing-requests", json={"buyer_id": buyer_id, "business_id": business_id, "amount_requested": amount_requested, "lender_name": lender_name}, headers={"Authorization": f"Bearer {LENDING_PARTNER_API_KEY}"})
        response.raise_for_status()
        return response.json()


async def get_financing_decision(submission_id: str) -> dict:
    async with httpx.AsyncClient(base_url=LENDING_PARTNER_BASE_URL, timeout=20.0) as client:
        response = await client.get(f"/financing-requests/{submission_id}", headers={"Authorization": f"Bearer {LENDING_PARTNER_API_KEY}"})
        response.raise_for_status()
        return response.json()