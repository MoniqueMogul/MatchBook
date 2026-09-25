class SignatureProviderError(Exception):
    """Base exception for signature provider failures."""


class SignatureProviderRequestError(SignatureProviderError):
    """The provider could not process the request."""


class SignatureProviderAuthenticationError(SignatureProviderError):
    """Provider authentication failed."""


class SignatureWebhookVerificationError(SignatureProviderError):
    """The webhook could not be verified."""


class SignatureDocumentNotFoundError(SignatureProviderError):
    """The provider document does not exist."""