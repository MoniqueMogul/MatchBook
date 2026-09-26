import os

from app.nda.signing.base import SignatureProvider
from app.nda.signing.enums import SignatureProviderType
from app.nda.signing.providers.signwell import SignWellProvider


def build_signature_provider() -> SignatureProvider:

    provider_name = os.getenv(
        "SIGNATURE_PROVIDER",
        "signwell",
    )

    try:
        provider_type = SignatureProviderType(
            provider_name
        )
    except ValueError as exc:
        raise RuntimeError(
            f"Unsupported signature provider: {provider_name}"
        ) from exc

    if provider_type == SignatureProviderType.SIGNWELL:

        api_key = os.getenv(
            "SIGNWELL_API_KEY"
        )

        template_id = os.getenv(
            "SIGNWELL_NDA_TEMPLATE_ID"
        )

        webhook_id = os.getenv(
            "SIGNWELL_WEBHOOK_ID"
        )

        test_mode = (
                os.getenv(
                    "SIGNWELL_TEST_MODE",
                    "true",
                ).lower()
                == "true"
        )

        if not api_key:
            raise RuntimeError(
                "SIGNWELL_API_KEY is not configured."
            )

        if not template_id:
            raise RuntimeError(
                "SIGNWELL_NDA_TEMPLATE_ID is not configured."
            )

        if not webhook_id:
            raise RuntimeError(
                "SIGNWELL_WEBHOOK_ID is not configured."
            )

        return SignWellProvider(
            api_key=api_key,
            template_id=template_id,
            webhook_id=webhook_id,
            test_mode=test_mode,
        )

    raise RuntimeError(
        f"Unsupported signature provider: {provider_type}"
    )