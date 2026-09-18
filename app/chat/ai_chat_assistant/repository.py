from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.db_model import (
    AIChatGeneration,
    Business,
    BuyerPreferences,
    BuyerProfile,
    Conversation,
    Match,
)


class AIAssistedChatRepositoryError(Exception):
    """Base exception for AI chat assistant repository errors."""


class AIChatContextNotFoundError(
    AIAssistedChatRepositoryError
):
    """Raised when required AI chat context cannot be found."""


class AIAssistedChatRepository:
    """
    Database access for the AI chat assistant.

    Responsibilities:
    - load trusted context for AI generation
    - persist AI generation observability records

    Does not:
    - generate prompts
    - call the LLM
    - calculate match scores
    - send chat messages
    - commit or rollback transactions
    """

    def __init__(
            self,
            session: Session,
    ) -> None:
        self.session = session

    # ========================================================
    # AI CONTEXT
    # ========================================================

    def get_match_context(
            self,
            *,
            conversation_id: UUID,
    ) -> tuple[
        Conversation,
        Match,
        BuyerProfile,
        BuyerPreferences,
        Business,
    ]:
        """
        Load trusted MatchBook records needed to generate
        an AI-assisted introduction.
        """

        statement = (
            select(
                Conversation,
                Match,
                BuyerProfile,
                BuyerPreferences,
                Business,
            )
            .join(
                Match,
                Conversation.match_id == Match.id,
            )
            .join(
                BuyerProfile,
                Match.buyer_id == BuyerProfile.id,
            )
            .join(
                BuyerPreferences,
                BuyerPreferences.buyer_id == BuyerProfile.id,
            )
            .join(
                Business,
                Match.business_id == Business.id,
            )
            .where(
                Conversation.id == conversation_id,
            )
        )

        result = self.session.execute(
            statement
        ).one_or_none()

        if result is None:
            raise AIChatContextNotFoundError(
                f"AI chat context could not be found for "
                f"conversation {conversation_id}."
            )

        (
            conversation,
            match,
            buyer,
            buyer_preferences,
            business,
        ) = result

        return (
            conversation,
            match,
            buyer,
            buyer_preferences,
            business,
        )

    # ========================================================
    # GENERATION PERSISTENCE
    # ========================================================

    def create_generation(
            self,
            *,
            user_id: UUID,
            conversation_id: UUID,
            match_id: UUID,
            model: str,
            prompt_version: str,
            success: bool,
            latency_ms: int | None = None,
            input_tokens: int | None = None,
            output_tokens: int | None = None,
            generated_message: str | None = None,
            error_code: str | None = None,
    ) -> AIChatGeneration:
        """
        Stage one AI generation record for persistence.

        Transaction ownership remains with the service/route.
        """

        generation = AIChatGeneration(
            user_id=user_id,
            conversation_id=conversation_id,
            match_id=match_id,

            model=model,
            prompt_version=prompt_version,

            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,

            success=success,
            generated_message=generated_message,
            error_code=error_code,
        )

        self.session.add(
            generation
        )

        self.session.flush()

        return generation
