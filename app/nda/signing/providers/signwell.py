from __future__ import annotations

from typing import Any

import httpx

from app.nda.signing.base import SignatureProvider
from app.nda.signing.enums import SignatureProviderType, SignerRole, SigningEventType
from app.nda.signing.exceptions import (
    SignatureProviderRequestError,
)
from app.nda.signing.schemas import (
    Signer,
    SigningDocument,
    SigningEvent,
    SigningSession,
)



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
        test_mode: bool = True,
        timeout: float = 15.0,
    ):
        self.api_key = api_key
        self.template_id = template_id
        self.test_mode = test_mode
        self.timeout = timeout



    async def create_document(
            self,
            *,
            signers: list[Signer],
            template_version: str,
            fields: dict[str, str],
    ) -> SigningDocument:

        recipients = []

        for signer in signers:
            placeholder_name = self._placeholder_for_role(
                signer.role
            )

            recipients.append(
                {
                    "id": self._recipient_id_for_role(
                        signer.role
                    ),
                    "placeholder_name": placeholder_name,
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
            },
        }

        # Only send template fields when we actually
        # have fields configured.
        if fields:
            payload["template_fields"] = (
                self._build_template_fields(fields)
            )

        data = await self._request(
            method="POST",
            url=(
                "https://www.signwell.com/api/v1/"
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
            recipients=data.get("recipients", []),
        )

        return SigningDocument(
            provider=SignatureProviderType.SIGNWELL,
            provider_document_id=provider_document_id,
            provider_template_id=self.template_id,
            status=data.get("status", "created"),
            signing_urls=signing_urls,
        )

    async def create_signing_session(
            self,
            *,
            provider_document_id: str,
            signer: Signer,
    ) -> SigningSession:

        data = await self._request(
            method="GET",
            url=(
                "https://www.signwell.com/api/v1/"
                f"documents/{provider_document_id}"
            ),
        )

        expected_recipient_id = (
            self._recipient_id_for_role(
                signer.role
            )
        )

        for recipient in data.get(
                "recipients",
                []
        ):

            if str(recipient.get("id")) != (
                    expected_recipient_id
            ):
                continue

            # Extra identity check.
            if recipient.get("email") != signer.email:
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
                provider_document_id=(
                    provider_document_id
                ),
                signing_url=signing_url,
            )

        raise SignatureProviderRequestError(
            "Signer was not found on the "
            "SignWell document."
        )
    async def get_document(
        self,
        *,
        provider_document_id: str,
    ) -> SigningDocument:
        raise NotImplementedError

    async def parse_webhook(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        raw_body: bytes,
    ) -> SigningEvent:
        raise NotImplementedError

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
                f"Signature provider unavailable: "
                f"{type(exc).__name__}"
            ) from exc

        if not response.is_success:
            raise SignatureProviderRequestError(
                f"Signature provider request failed: "
                f"HTTP {response.status_code}"
            )

        try:
            return response.json()

        except ValueError as exc:
            raise SignatureProviderRequestError(
                "Signature provider returned invalid JSON"
            ) from exc

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
    def _extract_signing_urls(
            *,
            recipients: list[dict],
    ) -> dict[SignerRole, str]:

        signing_urls: dict[SignerRole, str] = {}

        for recipient in recipients:

            recipient_id = str(
                recipient.get("id", "")
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


    @staticmethod
    def _build_template_fields(
            fields: dict[str, str],
    ) -> list[dict[str, str]]:

        return [
            {
                "api_id": field_name,
                "value": value,
            }
            for field_name, value in fields.items()
        ]