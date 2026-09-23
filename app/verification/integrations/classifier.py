from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from app.db.db_enum import DocumentType
from app.verification.config import VerificationSettings
from app.verification.exceptions import ProviderConfigurationError, ProviderError
from app.verification.schemas import DetectedDocumentClassification


class DocumentClassifier(Protocol):
    def classify(self, document_text: str) -> DetectedDocumentClassification: ...


class OpenAIDocumentClassifier:
    """Classifies type only; application code owns the match decision."""

    def __init__(self, settings: VerificationSettings) -> None:
        self.settings = settings

    def classify(self, document_text: str) -> DetectedDocumentClassification:
        if not self.settings.openai_api_key:
            raise ProviderConfigurationError("OpenAI is not configured")
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key)
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify the supplied document. Return only its "
                            "detected type and a confidence from 0 to 1."
                        ),
                    },
                    {
                        "role": "user",
                        "content": document_text,
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "document_type_classification",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "detected_type": {
                                    "type": "string",
                                    "enum": [value.value for value in DocumentType],
                                },
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                            },
                            "required": ["detected_type", "confidence"],
                            "additionalProperties": False,
                        },
                    },
                },
            )
            content = response.choices[0].message.content
            return DetectedDocumentClassification.model_validate(
                json.loads(content or "")
            )
        except ProviderConfigurationError:
            raise
        except (json.JSONDecodeError, ValidationError, KeyError, IndexError) as exc:
            raise ProviderError("Classifier returned invalid output") from exc
        except Exception as exc:
            raise ProviderError("Document classifier failed") from exc
