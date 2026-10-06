"""Read-only explanation of persisted deterministic matching evidence."""
import json
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.core.ai import ai_client, ai_model


class ExplanationText(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    explanation: str = Field(min_length=1, max_length=1200)


class MatchExplanationResponse(ExplanationText):
    match_id: UUID


class ExplanationBusy(Exception):
    pass


SYSTEM_PROMPT = """You explain an existing deterministic MatchBook FIT score to a buyer.

The FIT score has already been calculated. You must never calculate,
change, challenge, or estimate the score.

Use ONLY the supplied match evidence and buyer/business details.
Do not use outside knowledge.
Do not add market information.
Do not infer facts that are not explicitly present.
Do not mention "public context".
Do not describe missing information unless it directly affects the
provided match score.

Your job is to make the existing score understandable and useful.

Explain:
1. Why the strongest matching components make this business a good
   fit for this specific buyer.
2. Connect related evidence instead of listing component names.
   For example, explain what asking price + SDE + ARR alignment means
   together for the buyer.
3. Identify the most important trade-off or weaker component, if one
   exists, and explain exactly why it is weaker using only the
   supplied evidence.
4. End with a short overall explanation of why the resulting FIT
   score makes sense.

Prefer concrete values when they are provided:
- buyer target/preference
- business value
- component score
- overall FIT score

Do not say generic things such as:
"The financial areas align well."

Instead say things such as:
"The $1.2M asking price is within your $1.5M maximum, while the
business's $320K SDE exceeds your $250K preferred SDE."

Never invent a number that is not supplied.

Write directly to the buyer using "you" and "your".
Keep the explanation concise: approximately 2-4 short paragraphs.
Do not oversell the match."""

DIMENSIONS = {
    "industry": "industry", "geography": "geography", "purchase_price": "price",
    "sde": "sde", "arr": "arr", "owner_involvement": "owner_involvement",
    "customer_concentration": "customer_concentration",
    "transition_training": "transition_training", "deal_preference": "deal_preference",
}


def evidence_for(match):
    # Explicit allowlist excludes private seller data, documents and NDA-only details.
    components = {}
    for name, column in DIMENSIONS.items():
        stored = (match.score_breakdown or {}).get(name)
        if isinstance(stored, dict):
            values = {key: stored[key] for key in ("score", "weight", "contribution")
                      if isinstance(stored.get(key), (int, float)) and not isinstance(stored[key], bool)}
        else:
            values = {key: str(value) for key, value in {
                "score": getattr(match, f"{column}_score", None),
                "contribution": getattr(match, f"{column}_contribution", None),
            }.items() if value is not None}
        if "score" in values:
            components[name] = values
    if not components:
        return None
    return {
        "persisted_fit_score": str(match.score),
        "components": components,
        "current_public_business_context": {
            "industry": str(match.business.industry),
            "city": match.business.city, "state": match.business.state,
        },
    }


def generate_explanation(evidence, *, client=None):
    provider = client if client is not None else ai_client()
    response = provider.with_options(timeout=25.0, max_retries=0).responses.parse(
        model=ai_model(),
        input=[{"role": "system", "content": SYSTEM_PROMPT},
               {"role": "user", "content": json.dumps(evidence, allow_nan=False)}],
        text_format=ExplanationText,
        max_output_tokens=500,
    )
    if response.output_parsed is None:
        raise ValueError("No explanation returned")
    return ExplanationText.model_validate(response.output_parsed).explanation


def generate_for_buyer(evidence, *, user_id, match_id):
    # Share existing account-level daily quotas and token-owned Redis locks.
    from app.chat.ai_chat_assistant.rate_limit import AIChatRateLimiter, AIChatRateLimitError
    from app.core.redis import redis_client
    limiter = AIChatRateLimiter(redis_client)
    token = None
    reserved = False
    try:
        token = limiter.acquire_generation_lock(user_id=user_id, conversation_id=match_id)
        limiter.reserve_daily_generation(user_id=user_id)
        reserved = True
        result = generate_explanation(evidence)
        reserved = False  # Successful generation consumes its quota.
        return result
    except AIChatRateLimitError as exc:
        raise ExplanationBusy() from exc
    finally:
        if reserved:
            try:
                limiter.release_daily_generation(user_id=user_id)
            except Exception:
                pass
        if token:
            try:
                limiter.release_generation_lock(user_id=user_id, conversation_id=match_id, lock_token=token)
            except Exception:
                pass  # The existing Redis lock also expires automatically.
