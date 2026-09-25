from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.nda.signing.enums import SignatureProviderType, SignerRole, SigningEventType
from app.nda.signing.exceptions import SignatureWebhookVerificationError
from app.nda.signing.providers.signwell import SIGNWELL_EVENT_MAP
from app.nda.signing.schemas import (
    Signer,
    SigningDocument,
    SigningEvent,
    SigningSession,
)


class SignatureProvider(ABC):

    @abstractmethod
    async def create_document(
        self,
        *,
        signers: list[Signer],
        template_version: str,
        fields: dict[str, str],
    ) -> SigningDocument:
        """
        Create a signature document using the provider.

        The provider is responsible for mapping Matchbook's
        generic fields/signers into its own API format.
        """
        raise NotImplementedError

    @abstractmethod
    async def create_signing_session(
        self,
        *,
        provider_document_id: str,
        signer: Signer,
    ) -> SigningSession:
        """
        Return a signing session for one authenticated signer.

        Usually this means an embedded signing URL.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_document(
        self,
        *,
        provider_document_id: str,
    ) -> SigningDocument:
        """
        Retrieve the current provider-side document state.
        """
        raise NotImplementedError


    @abstractmethod
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

        if not event_name:
            raise SignatureWebhookVerificationError(
                "SignWell webhook is missing event type."
            )

        internal_event_type = (
            SIGNWELL_EVENT_MAP.get(event_name)
        )

        # Event is valid, but Matchbook does not care about it.
        if internal_event_type is None:
            return []

        # --------------------------------------------------------
        # Independently retrieve document from SignWell
        # --------------------------------------------------------

        verified_document = await self._get_document_data(
            provider_document_id=provider_document_id,
        )

        verified_document_id = verified_document.get("id")

        if verified_document_id != provider_document_id:
            raise SignatureWebhookVerificationError(
                "SignWell document verification failed."
            )

        # --------------------------------------------------------
        # Resolve signer
        # --------------------------------------------------------

        signer_email: str | None = None
        signer_role: SignerRole | None = None

        related_signer = event_data.get(
            "related_signer"
        )

        if isinstance(related_signer, dict):

            signer_email = related_signer.get(
                "email"
            )

            if signer_email:

                signer_role = self._resolve_signer_role(
                    document=verified_document,
                    signer_email=signer_email,
                )

                if signer_role is None:
                    raise SignatureWebhookVerificationError(
                        "Webhook signer does not belong "
                        "to the SignWell document."
                    )

        # document_signed MUST identify a signer.
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
                provider_event_id=event_data.get("hash"),
                provider_document_id=provider_document_id,
                signer_email=signer_email,
                signer_role=signer_role,
                occurred_at=occurred_at,
                metadata={
                    "provider_event_type": event_name,
                },
            )
        ]

        # --------------------------------------------------------
        # Independently retrieve document from SignWell
        # --------------------------------------------------------

        verified_document = await self._get_document_data(
            provider_document_id=provider_document_id,
        )

        verified_document_id = verified_document.get("id")

        if verified_document_id != provider_document_id:
            raise SignatureWebhookVerificationError(
                "SignWell document verification failed."
            )

        # --------------------------------------------------------
        # Resolve signer
        # --------------------------------------------------------

        signer_email: str | None = None
        signer_role: SignerRole | None = None

        related_signer = event_data.get(
            "related_signer"
        )

        if isinstance(related_signer, dict):

            signer_email = related_signer.get(
                "email"
            )

            if signer_email:

                signer_role = self._resolve_signer_role(
                    document=verified_document,
                    signer_email=signer_email,
                )

                if signer_role is None:
                    raise SignatureWebhookVerificationError(
                        "Webhook signer does not belong "
                        "to the SignWell document."
                    )

        # document_signed MUST identify a signer.
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
                provider_event_id=event_data.get("hash"),
                provider_document_id=provider_document_id,
                signer_email=signer_email,
                signer_role=signer_role,
                occurred_at=occurred_at,
                metadata={
                    "provider_event_type": event_name,
                },
            )
        ]

    async def _get_document_data(
            self,
            *,
            provider_document_id: str,
    ) -> dict[str, Any]:

        return await self._request(
            method="GET",
            url=(
                "https://www.signwell.com/api/v1/"
                f"documents/{provider_document_id}"
            ),
        )

    @staticmethod
    def _resolve_signer_role(
            *,
            document: dict[str, Any],
            signer_email: str | None,
    ) -> SignerRole | None:

        if not signer_email:
            return None

        normalized_email = signer_email.strip().lower()

        for recipient in document.get(
                "recipients",
                []
        ):

            recipient_email = (
                    recipient.get("email") or ""
            ).strip().lower()

            if recipient_email != normalized_email:
                continue

            recipient_id = str(
                recipient.get("id", "")
            )

            if recipient_id == "1":
                return SignerRole.BUYER

            if recipient_id == "2":
                return SignerRole.SELLER

        return None

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

        except (TypeError, ValueError, OverflowError):
            return None

