import os

import boto3
from botocore.client import Config

DEFAULT_BUCKET = os.environ.get("R2_BUCKET_NAME", "matchbook-documents")
_R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
_R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
_R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")

PRESIGNED_URL_EXPIRY_SECONDS = 15 * 60

_client = None


def _get_client():
    global _client
    if _client is None:
        if not (_R2_ACCOUNT_ID and _R2_ACCESS_KEY_ID and _R2_SECRET_ACCESS_KEY):
            raise RuntimeError("R2 credentials are not configured (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY).")
        _endpoint_url = f"https://{_R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        _client = boto3.client(
            "s3", endpoint_url=_endpoint_url, aws_access_key_id=_R2_ACCESS_KEY_ID,
            aws_secret_access_key=_R2_SECRET_ACCESS_KEY, config=Config(signature_version="s3v4"), region_name="auto",
        )
    return _client


def get_presigned_upload_url(bucket_name: str, object_key: str, content_type: str) -> str:
    return _get_client().generate_presigned_url("put_object", Params={"Bucket": bucket_name, "Key": object_key, "ContentType": content_type}, ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS)


def get_presigned_download_url(bucket_name: str, object_key: str) -> str:
    return _get_client().generate_presigned_url("get_object", Params={"Bucket": bucket_name, "Key": object_key}, ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS)


def get_object_bytes(bucket_name: str, object_key: str) -> bytes:
    response = _get_client().get_object(Bucket=bucket_name, Key=object_key)
    return response["Body"].read()


def delete_object(bucket_name: str, object_key: str) -> None:
    _get_client().delete_object(Bucket=bucket_name, Key=object_key)