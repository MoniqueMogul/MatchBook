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
