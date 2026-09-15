import json
import os
from typing import Optional

import openai

from app.db.db_enum import DocumentType
from app.verification.schemas.extraction import ClassificationResult, DocumentClassification

EXTRACTION_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

VALID_DOCUMENT_TYPES = ", ".join(dt.value for dt in DocumentType)

CLASSIFICATION_PROMPT_TEMPLATE = """\
Does this document appear to be a {expected_type}?

Valid document types: {valid_types}

Respond with ONLY valid JSON:
{{"detected_type": "<one of the valid types>", "matches_expected": true/false, "confidence": <0.0-1.0>}}

Document text:
{document_text}
"""


async def classify_document(
    document_id: str,
    expected_type: str,
    document_text: str,
) -> ClassificationResult:
    raw_output = await _call_classification_model(expected_type, document_text)
    parsed = _safe_json_parse(raw_output)

    classification = (
        DocumentClassification(**parsed)
        if parsed
        else DocumentClassification(detected_type="other", matches_expected=False, confidence=0.0)
    )

    return ClassificationResult(
        document_id=document_id,
        expected_type=expected_type,
        classification=classification,
        raw_model_output=raw_output,
    )


async def _call_classification_model(expected_type: str, document_text: str) -> str:
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set.")

    client = openai.AsyncOpenAI()
    response = await client.chat.completions.create(
        model=EXTRACTION_MODEL,
        messages=[
            {
                "role": "user",
                "content": CLASSIFICATION_PROMPT_TEMPLATE.format(
                    expected_type=expected_type,
                    valid_types=VALID_DOCUMENT_TYPES,
                    document_text=document_text,
                ),
            }
        ],
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


def _safe_json_parse(raw: str) -> Optional[dict]:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
