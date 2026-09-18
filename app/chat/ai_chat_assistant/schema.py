# app/chat/ai_chat_assistant/schema.py

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.db_enum import DealPreference


class AIAssistedChatModel(BaseModel):
    """
    Base model for AI-assisted chat data.
    """

    model_config = ConfigDict(
        extra="forbid",
    )


# ============================================================
# BUYER CONTEXT
# ============================================================


class AIBuyerContext(AIAssistedChatModel):
    """
    Buyer information that may be used when generating
    a conversation introduction.

    This deliberately contains only useful, non-sensitive
    matching context.
    """

    current_industry: str | None = None
    current_position: str | None = None
    business_experience_years: int | None = None
    relevant_experience: str | None = None

    target_industries: list[str] | None = None
    target_locations: list[dict] | None = None

    maximum_purchase_price: Decimal | None = None

    minimum_required_sde: Decimal | None = None
    preferred_sde: Decimal | None = None

    minimum_required_arr: Decimal | None = None
    preferred_arr: Decimal | None = None

    preferred_owner_hours_per_week: int | None = None
    required_transition_training_days: int | None = None

    deal_preference: DealPreference | None = None

    minimum_years_in_operation: int | None = None

    accepts_customer_concentration_above_25_percent: bool | None = None

    preferred_acquisition_timeline: str | None = None


# ============================================================
# BUSINESS CONTEXT
# ============================================================


class AIBusinessContext(AIAssistedChatModel):
    """
    Business information that may be used when generating
    a conversation introduction.
    """

    legal_name: str | None = None
    dba: str | None = None

    industry: str

    city: str
    county: str | None = None
    state: str

    asking_price: Decimal | None = None

    sde: Decimal | None = None
    arr: Decimal | None = None

    owner_involvement_hours_per_week: int | None = None
    transition_training_days: int | None = None

    deal_preference: DealPreference | None = None

    years_in_operation: int | None = None

    customer_concentration: Decimal | None = None

    preferred_sale_timeline: str | None = None


# ============================================================
# MATCH DIMENSION
# ============================================================


class AIMatchDimension(AIAssistedChatModel):
    """
    One deterministic reason contributing to the match.

    score:
        How well this dimension aligns, from 0 to 1.

    contribution:
        How much this dimension contributed to the final
        weighted FIT score.
    """

    dimension: str

    score: Decimal

    contribution: Decimal | None = None


# ============================================================
# MATCH CONTEXT
# ============================================================


class AIMatchContext(AIAssistedChatModel):
    """
    Deterministic matching information supplied to the AI.

    The AI does not calculate compatibility.
    It only explains existing matching results.
    """

    match_id: UUID

    score: Decimal

    dimensions: list[AIMatchDimension]

    matching_version: str


# ============================================================
# COMPLETE GENERATION CONTEXT
# ============================================================


class AIIntroductionContext(AIAssistedChatModel):
    """
    Complete trusted context used to generate an introduction.
    """

    conversation_id: UUID

    sender_role: Literal[
        "buyer",
        "seller",
    ]

    buyer: AIBuyerContext

    business: AIBusinessContext

    match: AIMatchContext


# ============================================================
# API REQUEST
# ============================================================


class AIIntroductionRequest(AIAssistedChatModel):
    """
    Optional instruction supplied by the user.

    Example:
        "Keep it short."

        "Ask about transition support."

    This is guidance only. It cannot replace trusted
    MatchBook context.
    """

    instruction: str | None = Field(
        default=None,
        max_length=500,
    )


# ============================================================
# LLM STRUCTURED OUTPUT
# ============================================================


class GeneratedIntroduction(AIAssistedChatModel):
    """
    Structured output expected from the language model.
    """

    message: str = Field(
        min_length=1,
        max_length=1500,
    )


# ============================================================
# API RESPONSE
# ============================================================


class AIIntroductionResponse(AIAssistedChatModel):
    """
    Suggestion returned to the frontend.

    This is only a draft. It is not persisted as a Message.
    """

    suggestion: str


# ============================================================
# LLM GENERATION METADATA
# ============================================================


class AIGenerationMetadata(AIAssistedChatModel):
    """
    Observability information about one LLM generation.

    This contains operational metadata only.
    It does not contain the prompt or MatchBook context.
    """

    model: str
    prompt_version: str

    latency_ms: int

    input_tokens: int | None = None
    output_tokens: int | None = None


# ============================================================
# INTERNAL LLM RESULT
# ============================================================


class AIIntroductionGenerationResult(AIAssistedChatModel):
    """
    Complete internal result returned by the LLM layer.

    The generated introduction and its observability metadata
    travel together so the service knows exactly how the
    suggestion was produced.
    """

    introduction: GeneratedIntroduction
    metadata: AIGenerationMetadata
