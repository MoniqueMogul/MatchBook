from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import hashlib
import hmac

import httpx

from app.nda.signing.base import SignatureProvider
from app.nda.signing.enums import (
    SignatureProviderType,
    SignerRole,
    SigningEventType,
)
from app.nda.signing.exceptions import (
    SignatureProviderRequestError,
    SignatureWebhookVerificationError,
)
from app.nda.signing.schemas import (
    Signer,
    SigningDocument,
    SigningEvent,
    SigningSession,
)


SIGNWELL_BASE_URL = "https://www.signwell.com/api/v1"


SIGNWELL_EVENT_MAP = {
    "document_signed": SigningEventType.SIGNER_SIGNED,
    "document_completed": SigningEventType.DOCUMENT_COMPLETED,
    "document_declined": SigningEventType.DOCUMENT_DECLINED,
    "document_expired": SigningEventType.DOCUMENT_EXPIRED,
}


class SignWellProvider(SignatureProvider):

    provider = SignatureProviderType.SIGNWELL

    def __init__(
            self,
            *,
            api_key: str,
            template_id: str,
            webhook_id: str,
            test_mode: bool = True,
            timeout: float = 15.0,
    ):
        self.api_key = api_key
        self.template_id = template_id
        self.webhook_id = webhook_id
        self.test_mode = test_mode
        self.timeout = timeout

    # ========================================================
    # CREATE DOCUMENT
    # ========================================================

    async def create_document(
            self,
            *,
            signers: list[Signer],
            template_version: str,
            reference_id: str,
            fields: dict[str, str],
    ) -> SigningDocument:

        recipients = []

        for signer in signers:

            recipients.append(
                {
                    "id": self._recipient_id_for_role(
                        signer.role
                    ),
                    "placeholder_name": self._placeholder_for_role(
                        signer.role
                    ),
                    "name": signer.name,
                    "email": signer.email,
                }
            )

        payload = {
            "test_mode": self.test_mode,
            "template_id": self.template_id,
            "embedded_signing": True,
            "recipients": recipients,
            "metadata": {
                "template_version": template_version,
                "matchbook_reference_id": reference_id,
            },
        }

        if fields:
            payload["template_fields"] = (
                self._build_template_fields(
                    fields
                )
            )

        data = await self._request(
            method="POST",
            url=(
                f"{SIGNWELL_BASE_URL}/"
                "document_templates/documents"
            ),
            json=payload,
        )

        provider_document_id = data.get("id")

        if not provider_document_id:
            raise SignatureProviderRequestError(
                "SignWell did not return a document ID."
            )

        signing_urls = self._extract_signing_urls(
            recipients=data.get(
                "recipients",
                [],
            ),
        )

        return SigningDocument(
            provider=SignatureProviderType.SIGNWELL,
            provider_document_id=provider_document_id,
            provider_template_id=self.template_id,
            status=data.get(
                "status",
                "created",
            ),
            signing_urls=signing_urls,
        )

    # ========================================================
    # SIGNING SESSION
    # ========================================================

    async def create_signing_session(
        self,
        *,
        provider_document_id: str,
        signer: Signer,
    ) -> SigningSession:

        data = await self._get_document_data(
            provider_document_id=provider_document_id,
        )

        expected_recipient_id = (
            self._recipient_id_for_role(
                signer.role
            )
        )

        for recipient in data.get(
            "recipients",
            [],
        ):

            if (
                str(recipient.get("id"))
                != expected_recipient_id
            ):
                continue

            recipient_email = (
                recipient.get("email") or ""
            ).strip().lower()

            signer_email = (
                signer.email
                .strip()
                .lower()
            )

            if recipient_email != signer_email:
                raise SignatureProviderRequestError(
                    "SignWell recipient identity does "
                    "not match the authenticated signer."
                )

            signing_url = recipient.get(
                "embedded_signing_url"
            )

            if not signing_url:
                raise SignatureProviderRequestError(
                    "SignWell did not return an "
                    "embedded signing URL."
                )

            return SigningSession(
                provider=SignatureProviderType.SIGNWELL,
                provider_document_id=provider_document_id,
                signing_url=signing_url,
            )

        raise SignatureProviderRequestError(
            "Signer was not found on the "
            "SignWell document."
        )

    # ========================================================
    # GET DOCUMENT
    # ========================================================

    async def get_document(
        self,
        *,
        provider_document_id: str,
    ) -> SigningDocument:

        data = await self._get_document_data(
            provider_document_id=provider_document_id,
        )

        returned_document_id = data.get("id")

        if not returned_document_id:
            raise SignatureProviderRequestError(
                "SignWell did not return a document ID."
            )

        return SigningDocument(
            provider=SignatureProviderType.SIGNWELL,
            provider_document_id=returned_document_id,
            provider_template_id=self.template_id,
            status=data.get(
                "status",
                "unknown",
            ),
            signing_urls=self._extract_signing_urls(
                recipients=data.get(
                    "recipients",
                    [],
                ),
            ),
        )

    # ========================================================
    # WEBHOOK
    # ========================================================

    async def parse_webhook(
            self,
            *,
            payload: dict[str, Any],
            headers: dict[str, str],
            raw_body: bytes,
    ) -> list[SigningEvent]:

        event_data = payload.get("event")
        data = payload.get("data")

        if not isinstance(event_data, dict):
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing event data."
            )

        # Authenticate the webhook BEFORE trusting its contents.
        self._verify_webhook_event(
            event_data=event_data,
        )

        if not isinstance(data, dict):
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing data."
            )

        webhook_document = data.get("object")

        if not isinstance(webhook_document, dict):
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing document data."
            )

        provider_document_id = webhook_document.get("id")

        if not provider_document_id:
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing document ID."
            )

        event_name = event_data.get("type")

        internal_event_type = SIGNWELL_EVENT_MAP.get(
            event_name
        )

        # Authenticated SignWell event, but Matchbook does
        # not care about this particular event type.
        if internal_event_type is None:
            return []

        # Second verification layer:
        # retrieve authoritative document state directly
        # from SignWell instead of trusting webhook document
        # contents for signer identity.
        verified_document = (
            await self._get_document_data(
                provider_document_id=provider_document_id,
            )
        )

        if (
                verified_document.get("id")
                != provider_document_id
        ):
            raise SignatureWebhookVerificationError(
                "SignWell document verification failed."
            )

        signer_email: str | None = None
        signer_role: SignerRole | None = None

        related_signer = event_data.get(
            "related_signer"
        )

        if isinstance(
                related_signer,
                dict,
        ):

            signer_email = related_signer.get(
                "email"
            )

            if signer_email:

                signer_role = (
                    self._resolve_signer_role(
                        document=verified_document,
                        signer_email=signer_email,
                    )
                )

                if signer_role is None:
                    raise SignatureWebhookVerificationError(
                        "Webhook signer does not belong "
                        "to the SignWell document."
                    )

        if (
                internal_event_type
                == SigningEventType.SIGNER_SIGNED
                and signer_role is None
        ):
            raise SignatureWebhookVerificationError(
                "SignWell signing event does not "
                "identify a valid signer."
            )

        occurred_at = self._parse_event_time(
            event_data.get("time")
        )

        return [
            SigningEvent(
                provider=SignatureProviderType.SIGNWELL,
                event_type=internal_event_type,
                provider_event_id=event_data.get(
                    "hash"
                ),
                provider_document_id=provider_document_id,
                signer_email=signer_email,
                signer_role=signer_role,
                occurred_at=occurred_at,
                metadata={
                    "provider_event_type": event_name,
                },
            )
        ]

    # ========================================================
    # HTTP
    # ========================================================

    async def _request(
        self,
        *,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
            ) as client:

                response = await client.request(
                    method=method,
                    url=url,
                    headers={
                        "X-Api-Key": self.api_key,
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=json,
                )

        except httpx.RequestError as exc:
            raise SignatureProviderRequestError(
                "Signature provider unavailable: "
                f"{type(exc).__name__}"
            ) from exc

        if not response.is_success:
            raise SignatureProviderRequestError(
                "Signature provider request failed: "
                f"HTTP {response.status_code}"
            )

        try:
            return response.json()

        except ValueError as exc:
            raise SignatureProviderRequestError(
                "Signature provider returned invalid JSON."
            ) from exc

    async def _get_document_data(
        self,
        *,
        provider_document_id: str,
    ) -> dict[str, Any]:

        return await self._request(
            method="GET",
            url=(
                f"{SIGNWELL_BASE_URL}/"
                f"documents/{provider_document_id}"
            ),
        )

    # ========================================================
    # SIGNER MAPPING
    # ========================================================

    @staticmethod
    def _placeholder_for_role(
        role: SignerRole,
    ) -> str:

        mapping = {
            SignerRole.BUYER: "Buyer",
            SignerRole.SELLER: "Seller",
        }

        try:
            return mapping[role]

        except KeyError as exc:
            raise SignatureProviderRequestError(
                f"Unsupported signer role: {role}"
            ) from exc

    @staticmethod
    def _recipient_id_for_role(
        role: SignerRole,
    ) -> str:

        mapping = {
            SignerRole.BUYER: "1",
            SignerRole.SELLER: "2",
        }

        try:
            return mapping[role]

        except KeyError as exc:
            raise SignatureProviderRequestError(
                f"Unsupported signer role: {role}"
            ) from exc

    @staticmethod
    def _resolve_signer_role(
        *,
        document: dict[str, Any],
        signer_email: str | None,
    ) -> SignerRole | None:

        if not signer_email:
            return None

        normalized_email = (
            signer_email
            .strip()
            .lower()
        )

        for recipient in document.get(
            "recipients",
            [],
        ):

            recipient_email = (
                recipient.get("email") or ""
            ).strip().lower()

            if recipient_email != normalized_email:
                continue

            recipient_id = str(
                recipient.get(
                    "id",
                    "",
                )
            )

            if recipient_id == "1":
                return SignerRole.BUYER

            if recipient_id == "2":
                return SignerRole.SELLER

        return None

    # ========================================================
    # SIGNING URLS
    # ========================================================

    @staticmethod
    def _extract_signing_urls(
        *,
        recipients: list[dict],
    ) -> dict[SignerRole, str]:

        signing_urls: dict[
            SignerRole,
            str,
        ] = {}

        for recipient in recipients:

            recipient_id = str(
                recipient.get(
                    "id",
                    "",
                )
            )

            signing_url = recipient.get(
                "embedded_signing_url"
            )

            if not signing_url:
                continue

            if recipient_id == "1":
                signing_urls[
                    SignerRole.BUYER
                ] = signing_url

            elif recipient_id == "2":
                signing_urls[
                    SignerRole.SELLER
                ] = signing_url

        return signing_urls

    # ========================================================
    # TEMPLATE FIELDS
    # ========================================================

    @staticmethod
    def _build_template_fields(
        fields: dict[str, str],
    ) -> list[dict[str, str]]:

        return [
            {
                "api_id": field_name,
                "value": value,
            }
            for field_name, value
            in fields.items()
        ]

    # ========================================================
    # EVENT TIME
    # ========================================================

    @staticmethod
    def _parse_event_time(
        value: Any,
    ) -> datetime | None:

        if value is None:
            return None

        try:
            return datetime.fromtimestamp(
                int(value),
                tz=timezone.utc,
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

    def _verify_webhook_event(
            self,
            *,
            event_data: dict[str, Any],
    ) -> None:

        event_type = event_data.get("type")
        event_time = event_data.get("time")
        received_hash = event_data.get("hash")

        if not isinstance(received_hash, str) or not received_hash:
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing or has an invalid event hash."
            )

        if not event_type:
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing event type."
            )

        if event_time is None:
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing event time."
            )

        if not received_hash:
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing event hash."
            )

        signed_payload = (
            f"{event_type}@{event_time}"
        ).encode("utf-8")

        calculated_hash = hmac.new(
            self.webhook_id.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
                calculated_hash,
                received_hash,
        ):
            raise SignatureWebhookVerificationError(
                "SignWell webhook hash verification failed."
            )