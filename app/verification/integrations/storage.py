from __future__ import annotations

from typing import Protocol

from app.verification.config import VerificationSettings
from app.verification.exceptions import ProviderConfigurationError, ProviderError


class DocumentStorage(Protocol):
    bucket_name: str

    def presign_upload(
        self,
        object_key: str,
        content_type: str,
    ) -> tuple[str, int]: ...

    def object_exists(self, object_key: str) -> bool: ...

    def get_bytes(self, object_key: str) -> bytes: ...


class R2DocumentStorage:
    """Cloudflare R2 adapter using its S3-compatible API."""

    expires_in_seconds = 15 * 60

    def __init__(self, settings: VerificationSettings) -> None:
        self.settings = settings
        self.bucket_name = settings.r2_bucket_name
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not all(
            (
                self.settings.r2_account_id,
                self.settings.r2_access_key_id,
                self.settings.r2_secret_access_key,
                self.bucket_name,
            )
        ):
            raise ProviderConfigurationError("R2 is not configured")
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:
            raise ProviderConfigurationError(
                "R2 support requires boto3"
            ) from exc
        self._client = boto3.client(
            "s3",
            endpoint_url=(
                f"https://{self.settings.r2_account_id}."
                "r2.cloudflarestorage.com"
            ),
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        return self._client

    def presign_upload(
        self,
        object_key: str,
        content_type: str,
    ) -> tuple[str, int]:
        try:
            url = self._get_client().generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key,
                    "ContentType": content_type,
                },
                ExpiresIn=self.expires_in_seconds,
            )
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            raise ProviderError("Unable to create R2 upload URL") from exc
        return url, self.expires_in_seconds

    def object_exists(self, object_key: str) -> bool:
        try:
            self._get_client().head_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )
            return True
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise ProviderError("Unable to inspect R2 object") from exc

    def get_bytes(self, object_key: str) -> bytes:
        try:
            response = self._get_client().get_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )
            return response["Body"].read()
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            raise ProviderError("Unable to retrieve R2 object") from exc
