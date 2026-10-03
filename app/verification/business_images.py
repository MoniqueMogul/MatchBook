"""Sign business photos only after the caller has authorized business access."""
import logging
from uuid import UUID

from app.verification.config import VerificationSettings
from app.verification.exceptions import ProviderConfigurationError, ProviderError
from app.verification.integrations.storage import R2DocumentStorage

logger = logging.getLogger(__name__)


def business_image_url(business_id: UUID, object_key: str | None) -> str | None:
    # Never sign a user's personal image or another business's object.
    prefix = f"profile-images/businesses/{business_id}/"
    if not object_key or not object_key.startswith(prefix) or object_key == prefix:
        return None
    try:
        storage = R2DocumentStorage(VerificationSettings.from_env())
        url, _ = storage.presign_download(object_key)
        return url
    except (ProviderConfigurationError, ProviderError):
        # A photo outage must not make matches or conversations unavailable.
        logger.warning("Business photo unavailable for business %s", business_id)
        return None
