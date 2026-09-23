from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Protocol

import httpx

from app.db.db_enum import VerificationStatus
from app.verification.config import VerificationSettings
from app.verification.exceptions import ProviderConfigurationError, ProviderError
from app.verification.schemas import (
    DiditResult,
    IdentityWorkflow,
    ProviderSession,
)


class DiditProvider(Protocol):
    async def create_session(
        self,
        workflow: IdentityWorkflow,
        vendor_data: str,
    ) -> ProviderSession: ...


class DiditClient:
    base_url = "https://verification.didit.me"

    def __init__(self, settings: VerificationSettings) -> None:
        self.settings = settings

    async def create_session(
        self,
        workflow: IdentityWorkflow,
        vendor_data: str,
    ) -> ProviderSession:
        if not self.settings.didit_api_key:
            raise ProviderConfigurationError("Didit is not configured")
        workflow_id = self._workflow_ids().get(workflow)
        if not workflow_id:
            raise ProviderConfigurationError(
                f"Didit workflow is not configured: {workflow.value}"
            )
        payload = {
            "workflow_id": workflow_id,
            "vendor_data": vendor_data,
        }
        if self.settings.didit_callback_url:
            payload["callback"] = self.settings.didit_callback_url
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=20.0,
            ) as client:
                response = await client.post(
                    "/v3/session/",
                    json=payload,
                    headers={
                        "x-api-key": self.settings.didit_api_key,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
            return ProviderSession(
                session_id=data["session_id"],
                url=data["url"],
                workflow=workflow,
            )
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            raise ProviderError("Didit session creation failed") from exc

    def parse_webhook(self, payload: dict[str, Any]) -> DiditResult:
        workflow_ids = {
            value: key
            for key, value in self._workflow_ids().items()
            if value
        }
        try:
            workflow = workflow_ids[payload["workflow_id"]]
            provider_status = str(payload["status"])
            status = map_didit_status(provider_status)
            session_id = str(payload["session_id"])
            vendor_data = str(payload["vendor_data"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Didit webhook payload was invalid") from exc
        if not session_id or not vendor_data:
            raise ProviderError("Didit webhook payload was invalid")
        return DiditResult(
            session_id=session_id,
            workflow=workflow,
            status=status,
            vendor_data=vendor_data,
            provider_status=provider_status,
        )

    def verify_webhook(
        self,
        payload: dict[str, Any],
        signature: str,
        timestamp_header: str | None,
        *,
        now: float | None = None,
    ) -> bool:
        secret = self.settings.didit_webhook_secret
        if not secret or not signature:
            return False
        payload_timestamp = payload.get("timestamp")
        try:
            timestamp = int(payload_timestamp)
        except (TypeError, ValueError):
            return False
        if timestamp_header is not None and timestamp_header != str(timestamp):
            return False
        current = time.time() if now is None else now
        if abs(current - timestamp) > 300:
            return False
        canonical = canonical_json(payload).encode("utf-8")
        expected = hmac.new(
            secret.encode("utf-8"),
            canonical,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _workflow_ids(self) -> dict[IdentityWorkflow, str]:
        return {
            IdentityWorkflow.INDIVIDUAL_KYC: self.settings.didit_kyc_workflow_id,
            IdentityWorkflow.EIN_CHECK: self.settings.didit_ein_workflow_id,
            IdentityWorkflow.FULL_KYB: self.settings.didit_kyb_workflow_id,
        }


def map_didit_status(value: str) -> VerificationStatus:
    normalized = value.strip().lower().replace("_", " ")
    mapping = {
        "not started": VerificationStatus.UNVERIFIED,
        "in progress": VerificationStatus.PENDING,
        "in review": VerificationStatus.REQUIRES_REVIEW,
        "approved": VerificationStatus.VERIFIED,
        "declined": VerificationStatus.FAILED,
        "resubmission requested": VerificationStatus.REQUIRES_REVIEW,
        "abandoned": VerificationStatus.FAILED,
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise ProviderError("Unknown Didit status") from exc


def canonical_json(payload: Any) -> str:
    return json.dumps(
        _normalize_numbers(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _normalize_numbers(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_numbers(item) for item in value]
    return value
