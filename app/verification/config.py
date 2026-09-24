from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationSettings:
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "matchbook-private"
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_environment: str = "sandbox"
    didit_api_key: str = ""
    didit_webhook_secret: str = ""
    didit_kyc_workflow_id: str = ""
    didit_ein_workflow_id: str = ""
    didit_kyb_workflow_id: str = ""
    didit_callback_url: str | None = None
    classification_confidence_threshold: float = 0.80
    max_classifier_characters: int = 50_000
    max_document_bytes: int = 20 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "VerificationSettings":
        return cls(
            r2_account_id=os.getenv("R2_ACCOUNT_ID", ""),
            r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
            r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
            r2_bucket_name=os.getenv("R2_BUCKET_NAME", "matchbook-private"),
            plaid_client_id=os.getenv("PLAID_CLIENT_ID", ""),
            plaid_secret=os.getenv("PLAID_SECRET", ""),
            plaid_environment=os.getenv("PLAID_ENV", "sandbox"),
            didit_api_key=os.getenv("DIDIT_API_KEY", ""),
            didit_webhook_secret=os.getenv("DIDIT_WEBHOOK_SECRET", ""),
            didit_kyc_workflow_id=os.getenv("DIDIT_WORKFLOW_KYC", ""),
            didit_ein_workflow_id=os.getenv("DIDIT_WORKFLOW_EIN", ""),
            didit_kyb_workflow_id=os.getenv("DIDIT_WORKFLOW_KYB", ""),
            didit_callback_url=os.getenv("DIDIT_CALLBACK_URL") or None,
        )
