from pydantic import BaseModel, Field


class DocumentClassification(BaseModel):
    detected_type: str = Field(
        ...,
        description="The document type the model detected in the uploaded file.",
    )
    matches_expected: bool = Field(
        ...,
        description="Whether the detected type matches the expected document type.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence in the classification (0.0–1.0).",
    )


class ClassificationResult(BaseModel):
    document_id: str
    expected_type: str
    classification: DocumentClassification
    raw_model_output: str | None = None
