from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.db_enum import DocumentType, VerificationStatus


class DocumentUploadRequest(BaseModel):
    expected_document_type: DocumentType
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str
    file_size: int = Field(gt=0)
    buyer_financials_id: UUID | None = None
    business_financials_id: UUID | None = None
    declaration_signed: bool = False

    @model_validator(mode="after")
    def validate_owner(self) -> "DocumentUploadRequest":
        owner_count = sum(
            value is not None
            for value in (
                self.buyer_financials_id,
                self.business_financials_id,
            )
        )
        if owner_count != 1:
            raise ValueError(
                "Exactly one of buyer_financials_id or "
                "business_financials_id is required"
            )
        return self


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    upload_url: str
    required_headers: dict[str, str]
    expires_in_seconds: int


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_type: DocumentType
    original_filename: str | None
    mime_type: str | None
    file_size: int | None
    verification_status: VerificationStatus
    verification_provider: str | None
    verified_at: datetime | None
    document_metadata: dict[str, Any] | None
    uploaded_at: datetime


class DetectedDocumentClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)


class DocumentDecision(BaseModel):
    expected_type: DocumentType
    detected_type: DocumentType
    confidence: float
    matches_expected: bool
    status: VerificationStatus
    reason_code: str


class DocumentGateAssessment(BaseModel):
    readable_text_extracted: bool
    business_identity_match: bool | None
    reporting_period_identified: bool | None
    reporting_years: list[int] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)


class PlaidPublicTokenRequest(BaseModel):
    public_token: str = Field(min_length=1, max_length=2048)


class PlaidLinkTokenResponse(BaseModel):
    link_token: str
    expiration: str | None = None


class PlaidFundsResponse(BaseModel):
    buyer_financials_id: UUID
    eligible_balance: float
    eligible_account_count: int
    verification_status: VerificationStatus


class IdentityWorkflow(str, Enum):
    INDIVIDUAL_KYC = "individual_kyc"
    EIN_CHECK = "ein_check"
    FULL_KYB = "full_kyb"


class ProviderSession(BaseModel):
    session_id: str
    url: str
    workflow: IdentityWorkflow


class VerificationStatusResponse(BaseModel):
    entity_id: UUID
    status: VerificationStatus
    provider: str | None = None


class NDAIneligibilityReason(str, Enum):
    BUYER_KYC = "buyer_kyc"
    BUYER_FINANCIAL_VERIFICATION = "buyer_financial_verification"
    SELLER_KYC = "seller_kyc"
    BUSINESS_KYB = "business_kyb"
    BUSINESS_FINANCIAL_VERIFICATION = "business_financial_verification"


class NDAEligibilityResult(BaseModel):
    eligible: bool
    missing: list[NDAIneligibilityReason] = Field(default_factory=list)


class DiditResult(BaseModel):
    session_id: str
    workflow: IdentityWorkflow
    status: VerificationStatus
    vendor_data: str
    provider_status: str
