"""Wraps Didit's Sessions API for KYC/EIN/KYB verification."""

import hashlib
import hmac
import os
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import BaseModel

DIDIT_BASE_URL = "https://verification.didit.me"
DIDIT_API_KEY = os.environ.get("DIDIT_API_KEY", "")
DIDIT_WEBHOOK_SECRET = os.environ.get("DIDIT_WEBHOOK_SECRET", "")

WORKFLOW_IDS = {
    "individual_kyc": os.environ.get("DIDIT_WORKFLOW_KYC", ""),
    "ein_check": os.environ.get("DIDIT_WORKFLOW_EIN", ""),
    "full_kyb": os.environ.get("DIDIT_WORKFLOW_KYB", ""),
}


class DiditSessionStatus(str, Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    APPROVED = "Approved"
    DECLINED = "Declined"
    RESUBMISSION_REQUESTED = "Resubmission Requested"


class VerificationSession(BaseModel):
    session_id: str
    url: str
    token: Optional[str] = None
    workflow_type: str


class NormalizedVerificationResult(BaseModel):
    session_id: str
    workflow_type: str
    status: DiditSessionStatus
    session_kind: str
    vendor_data: Optional[str] = None
    raw_payload: dict[str, Any]


def _headers() -> dict[str, str]:
    return {"x-api-key": DIDIT_API_KEY, "Content-Type": "application/json"}


async def create_session(
    workflow_type: str, vendor_data: str, callback_url: Optional[str] = None
) -> VerificationSession:
    if workflow_type not in WORKFLOW_IDS:
        raise ValueError(f"Unknown workflow_type: {workflow_type}")

    payload = {"workflow_id": WORKFLOW_IDS[workflow_type], "vendor_data": vendor_data}
    if callback_url:
        payload["callback"] = callback_url

    async with httpx.AsyncClient(base_url=DIDIT_BASE_URL, timeout=15.0) as client:
        response = await client.post("/v3/session/", json=payload, headers=_headers())
        response.raise_for_status()
        data = response.json()

    return VerificationSession(
        session_id=data["session_id"], url=data["url"], token=data.get("token"),
        workflow_type=workflow_type,
    )


async def get_session_status(session_id: str) -> NormalizedVerificationResult:
    async with httpx.AsyncClient(base_url=DIDIT_BASE_URL, timeout=15.0) as client:
        response = await client.get(f"/v3/session/{session_id}/", headers=_headers())
        response.raise_for_status()
        data = response.json()
    return _normalize(data)


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    if not DIDIT_WEBHOOK_SECRET:
        return False
    expected = hmac.new(DIDIT_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_webhook(payload: dict[str, Any]) -> NormalizedVerificationResult:
    return _normalize(payload)


def _normalize(data: dict[str, Any]) -> NormalizedVerificationResult:
    workflow_id = data.get("workflow_id", "")
    workflow_type = next((k for k, v in WORKFLOW_IDS.items() if v == workflow_id), "unknown")
    return NormalizedVerificationResult(
        session_id=data["session_id"], workflow_type=workflow_type,
        status=DiditSessionStatus(data["status"]),
        session_kind=data.get("session_kind", "individual"),
        vendor_data=data.get("vendor_data"), raw_payload=data,
    )