from typing import Optional

from pydantic import BaseModel, Field


class ExtractedFinancialFields(BaseModel):
    year: Optional[int] = None
    revenue: Optional[float] = None
    sde: Optional[float] = None
    ebitda: Optional[float] = None
    reporting_period_start: Optional[str] = None
    reporting_period_end: Optional[str] = None


class ExtractedIdentityFields(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    id_number: Optional[str] = None
    issuing_country: Optional[str] = None
    expiry_date: Optional[str] = None


class FieldConfidence(BaseModel):
    field: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    document_id: str
    document_type: str
    financial_fields: Optional[ExtractedFinancialFields] = None
    identity_fields: Optional[ExtractedIdentityFields] = None
    field_confidences: list[FieldConfidence] = []
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    raw_model_output: Optional[str] = None