from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.nda.signing.enums import (
    SignatureProviderType,
    SignerRole,
    SigningEventType,
)


@dataclass(frozen=True)
class Signer:
    user_id: UUID
    role: SignerRole
    name: str
    email: str


@dataclass(frozen=True)
class SigningDocument:
    provider: SignatureProviderType
    provider_document_id: str
    provider_template_id: str | None
    status: str

    # Provider-independent mapping:
    # buyer -> embedded URL
    # seller -> embedded URL
    signing_urls: dict[SignerRole, str] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class SigningSession:
    provider: SignatureProviderType
    provider_document_id: str
    signing_url: str


@dataclass(frozen=True)
class SigningEvent:
    provider: SignatureProviderType
    event_type: SigningEventType
    provider_event_id: str | None
    provider_document_id: str

    signer_email: str | None = None
    signer_role: SignerRole | None = None
    occurred_at: datetime | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )