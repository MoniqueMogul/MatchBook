from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.verification.schemas import NDAIneligibilityReason


class VerificationError(Exception):
    """Base class for expected verification failures."""


class ResourceNotFoundError(VerificationError):
    """The requested resource does not exist or is not owned by the caller."""


class InvalidVerificationRequest(VerificationError):
    """The requested transition or input is invalid."""


class ProviderConfigurationError(VerificationError):
    """A provider is not configured."""


class ProviderError(VerificationError):
    """A provider returned an error or malformed response."""


class DocumentExtractionError(VerificationError):
    """Document text could not be extracted safely."""


class NDAEligibilityError(VerificationError):
    """A match cannot proceed to NDA because verification is incomplete."""

    def __init__(self, missing: list[NDAIneligibilityReason]) -> None:
        self.missing = list(missing)
        super().__init__("Match is not eligible for NDA")
