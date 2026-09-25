from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

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
        """
        Parse a provider-specific webhook into Matchbook's
        generic signing events.
        """
        raise NotImplementedError