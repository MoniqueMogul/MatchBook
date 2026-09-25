from enum import StrEnum


class SignatureProviderType(StrEnum):
    SIGNWELL = "signwell"
    DOCUSIGN = "docusign"
    DROPBOX_SIGN = "dropbox_sign"


class SignerRole(StrEnum):
    BUYER = "buyer"
    SELLER = "seller"


class SigningEventType(StrEnum):
    SIGNER_SIGNED = "signer_signed"
    DOCUMENT_COMPLETED = "document_completed"
    DOCUMENT_DECLINED = "document_declined"
    DOCUMENT_EXPIRED = "document_expired"