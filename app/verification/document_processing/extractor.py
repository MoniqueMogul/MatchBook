import json
import os
from typing import Optional

import openai

from app.verification.schemas.extraction import ExtractedFinancialFields, ExtractionResult, FieldConfidence

EXTRACTION_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

EXTRACTION_PROMPT_TEMPLATE = """\
Extract the following fields from this financial document if present:
year, revenue, sde, ebitda, reporting_period_start, reporting_period_end.
Return ONLY valid JSON, null for any field not found:
{{"year": null, "revenue": null, "sde": null, "ebitda": null, "reporting_period_start": null, "reporting_period_end": null}}

Document text:
{document_text}
"""


async def extract_financial_fields(document_id: str, document_text: str) -> ExtractionResult:
    raw_output = await _call_extraction_model(document_text)
    parsed = _safe_json_parse(raw_output)
    financial_fields = ExtractedFinancialFields(**parsed) if parsed else None

    confidences = [FieldConfidence(field=k, confidence=0.85) for k, v in parsed.items() if v is not None] if parsed else []
    overall_confidence = sum(c.confidence for c in confidences) / len(confidences) if confidences else 0.0

    return ExtractionResult(
        document_id=document_id, document_type="financial_document", financial_fields=financial_fields,
        field_confidences=confidences, overall_confidence=overall_confidence, raw_model_output=raw_output,
    )


async def _call_extraction_model(document_text: str) -> str:
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set.")

    client = openai.AsyncOpenAI()
    # TODO: wrap this call with Langfuse's @observe decorator once the
    # open-source Langfuse instance is configured.
    response = await client.chat.completions.create(
        model=EXTRACTION_MODEL,
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT_TEMPLATE.format(
                    document_text=document_text
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