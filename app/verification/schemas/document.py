from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.db_enum import DocumentType, VerificationStatus


class DocumentUploadRequest(BaseModel):
    document_type: DocumentType
    original_filename: str
    mime_type: str
    file_size: int
    declaration_signed: bool  # seller must confirm authenticity
    buyer_financials_id: Optional[UUID] = None
    business_financials_id: Optional[UUID] = None
    nda_id: Optional[UUID] = None


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    upload_url: str = Field(..., description="Presigned R2 URL the client uploads the file to directly")
    object_key: str


class DocumentOut(BaseModel):
    id: UUID
    document_type: DocumentType
    original_filename: Optional[str]
    mime_type: Optional[str]
    file_size: Optional[int]
    verification_status: VerificationStatus
    verification_provider: Optional[str]
    verified_at: Optional[datetime]
    declaration_signed: bool
    declaration_signed_at: Optional[datetime]
    document_metadata: Optional[dict[str, Any]]
    uploaded_at: datetime

    class Config:
        from_attributes = True