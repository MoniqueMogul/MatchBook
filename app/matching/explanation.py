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


SYSTEM_PROMPT = """You are MatchBook's buyer-facing match explanation assistant.

MatchBook has already calculated a deterministic FIT score using the
buyer's acquisition preferences and the business's information.

You DO NOT calculate, modify, challenge, estimate, or reproduce the
FIT score.

Your job is to translate the evidence behind that score into a clear,
useful explanation of why this business may or may not fit what this
specific buyer is looking for.

IMPORTANT AUDIENCE:
You are speaking to a business buyer, not an engineer, data scientist,
or MatchBook employee.

Never expose or explain internal scoring mechanics.

DO NOT mention:
- component scores such as 1.0, 0.8, or 0.65
- component weights such as 0.30
- normalized values
- scoring formulas
- internal field names
- "evaluated components"
- technical matching terminology
- how much a component contributed mathematically to the score

You may use this information internally to understand which areas are
stronger or weaker, but translate it into normal business language.

USE ONLY THE PROVIDED EVIDENCE.

Do not:
- use outside knowledge
- invent facts
- make assumptions about the business
- add market commentary
- mention public context
- claim something is good or bad unless the supplied evidence supports it

Whenever actual buyer and business values are provided, prefer those
values over vague statements.

For example, instead of:

"Purchase price scored 1.0."

say:

"The asking price is within the maximum budget you set."

Even better, when values are available:

"The $1.2M asking price is within your $1.5M acquisition budget."

Instead of:

"Owner involvement scored 0.85."

say:

"The business requires slightly more day-to-day involvement than you
prefer, making this one area where the fit is not exact."

STRUCTURE:

Start by explaining the most important reasons this business fits what
the buyer is looking for.

Group related criteria into meaningful ideas rather than walking
through the scoring fields one by one.

Useful groups may include:
- financial fit
- how the business would fit the buyer's desired involvement
- transition/handoff expectations
- customer concentration
- deal structure

Then clearly explain any meaningful trade-offs or areas where the
business differs from the buyer's preferences.

If there are no meaningful trade-offs in the supplied match evidence,
say that naturally without discussing component scores.

Finish with one concise sentence explaining what the overall match
means for this buyer.

Write directly to the buyer using "you" and "your".

Tone:
Clear, confident, practical, and conversational.
Do not sound like a technical report.
Do not oversell the business.
Do not use marketing hype.

Length:
2-3 short paragraphs."""

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
