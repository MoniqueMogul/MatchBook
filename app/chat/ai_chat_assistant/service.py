from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.chat.ai_chat_assistant.llm import AIIntroductionLLM, AIIntroductionGenerationError
from app.chat.ai_chat_assistant.repository import (
    AIAssistedChatRepository,
)
from app.chat.ai_chat_assistant.schema import (
    AIBusinessContext,
    AIBuyerContext,
    AIIntroductionContext,
    AIMatchContext,
    AIMatchDimension, AIIntroductionResponse, AIIntroductionRequest,
)
from app.chat.repository import ChatRepository
from app.db.db_model import (
    Business,
    BuyerPreferences,
    BuyerProfile,
    Match,
)


class AIAssistedChatService:
    """
    Business logic for AI-assisted chat.

    Responsibilities:
    - verify conversation access
    - load trusted MatchBook data
    - determine whether the sender is the buyer or seller
    - convert ORM records into controlled AI context

    Does not:
    - calculate match scores
    - persist AI-generated messages
    - send chat messages
    - call the LLM directly
    """

    def __init__(
            self,
            session: Session,
            *,
            llm: AIIntroductionLLM | None = None,
    ) -> None:
        self.session = session

        self.repository = AIAssistedChatRepository(
            session
        )

        self.llm = llm or AIIntroductionLLM()

    # ========================================================
    # BUILD INTRODUCTION CONTEXT
    # ========================================================

    def build_introduction_context(
            self,
            *,
            conversation_id: UUID,
            user_id: UUID,
    ) -> AIIntroductionContext:
        """
        Build trusted context for an AI-generated introduction.
        """

        (
            conversation,
            match,
            buyer,
            buyer_preferences,
            business,
        ) = self.repository.get_match_context(
            conversation_id=conversation_id,
        )

        # Security check must happen before returning any
        # buyer/business/match context.
        self._require_conversation_access(
            match=match,
            user_id=user_id,
        )

        sender_role = self._get_sender_role(
            buyer=buyer,
            business=business,
            user_id=user_id,
        )

        buyer_context = self._build_buyer_context(
            buyer=buyer,
            preferences=buyer_preferences,
        )

        business_context = self._build_business_context(
            business=business,
        )

        match_context = self._build_match_context(
            match=match,
        )

        return AIIntroductionContext(
            conversation_id=conversation.id,
            sender_role=sender_role,
            buyer=buyer_context,
            business=business_context,
            match=match_context,
        )

    # ========================================================
    # ACCESS
    # ========================================================

    def _require_conversation_access(
            self,
            *,
            match: Match,
            user_id: UUID,
    ) -> None:
        """
        Verify that the authenticated user belongs to this match.
        """

        buyer_user_id = match.buyer.user_id
        seller_user_id = match.business.seller.user_id

        if user_id not in {
            buyer_user_id,
            seller_user_id,
        }:
            raise PermissionError(
                "You do not have access to this conversation."
            )

    # ========================================================
    # SENDER ROLE
    # ========================================================

    def _get_sender_role(
            self,
            *,
            buyer: BuyerProfile,
            business: Business,
            user_id: UUID,
    ) -> str:
        """
        Determine which side of the match is requesting
        the AI suggestion.
        """

        if buyer.user_id == user_id:
            return "buyer"

        if business.seller.user_id == user_id:
            return "seller"

        raise PermissionError(
            "User does not belong to this match."
        )

    # ========================================================
    # BUYER CONTEXT
    # ========================================================

    def _build_buyer_context(
            self,
            *,
            buyer: BuyerProfile,
            preferences: BuyerPreferences,
    ) -> AIBuyerContext:
        """
        Convert buyer ORM records into safe AI context.
        """

        return AIBuyerContext(
            current_industry=buyer.current_industry,
            current_position=buyer.current_position,
            business_experience_years=buyer.business_experience_years,
            relevant_experience=buyer.relevant_experience,

            target_industries=preferences.target_industries,
            target_locations=preferences.target_locations,

            maximum_purchase_price=preferences.maximum_purchase_price,

            minimum_required_sde=preferences.minimum_required_sde,
            preferred_sde=preferences.preferred_sde,

            minimum_required_arr=preferences.minimum_required_arr,
            preferred_arr=preferences.preferred_arr,

            preferred_owner_hours_per_week=(
                preferences.preferred_owner_hours_per_week
            ),

            required_transition_training_days=(
                preferences.required_transition_training_days
            ),

            deal_preference=preferences.deal_preference,

            minimum_years_in_operation=(
                preferences.minimum_years_in_operation
            ),

            accepts_customer_concentration_above_25_percent=(
                preferences
                .accepts_customer_concentration_above_25_percent
            ),

            preferred_acquisition_timeline=(
                preferences.preferred_acquisition_timeline
            ),
        )

    # ========================================================
    # BUSINESS CONTEXT
    # ========================================================

    def _build_business_context(
            self,
            *,
            business: Business,
    ) -> AIBusinessContext:
        """
        Convert the Business ORM record into safe AI context.
        """

        return AIBusinessContext(
            legal_name=business.legal_name,
            dba=business.dba,

            industry=business.industry,

            city=business.city,
            county=business.county,
            state=business.state,

            asking_price=business.asking_price,

            sde=business.sde,
            arr=business.arr,

            owner_involvement_hours_per_week=(
                business.owner_involvement_hours_per_week
            ),

            transition_training_days=(
                business.transition_training_days
            ),

            deal_preference=business.deal_preference,

            years_in_operation=business.years_in_operation,

            customer_concentration=(
                business.customer_concentration
            ),

            preferred_sale_timeline=(
                business.preferred_sale_timeline
            ),
        )

    # ========================================================
    # MATCH CONTEXT
    # ========================================================

    def _build_match_context(
            self,
            *,
            match: Match,
    ) -> AIMatchContext:
        """
        Convert persisted deterministic Match results into
        context that the AI can explain.

        No matching calculations happen here.
        """

        dimensions = [
            self._make_dimension(
                name="industry",
                score=match.industry_score,
                contribution=match.industry_contribution,
            ),
            self._make_dimension(
                name="geography",
                score=match.geography_score,
                contribution=match.geography_contribution,
            ),
            self._make_dimension(
                name="price",
                score=match.price_score,
                contribution=match.price_contribution,
            ),
            self._make_dimension(
                name="sde",
                score=match.sde_score,
                contribution=match.sde_contribution,
            ),
            self._make_dimension(
                name="arr",
                score=match.arr_score,
                contribution=match.arr_contribution,
            ),
            self._make_dimension(
                name="owner_involvement",
                score=match.owner_involvement_score,
                contribution=match.owner_involvement_contribution,
            ),
            self._make_dimension(
                name="customer_concentration",
                score=match.customer_concentration_score,
                contribution=(
                    match.customer_concentration_contribution
                ),
            ),
            self._make_dimension(
                name="transition_training",
                score=match.transition_training_score,
                contribution=(
                    match.transition_training_contribution
                ),
            ),
            self._make_dimension(
                name="deal_preference",
                score=match.deal_preference_score,
                contribution=(
                    match.deal_preference_contribution
                ),
            ),
        ]

        # Some dimensions can legitimately be None because they
        # were not applicable to this particular match.
        applicable_dimensions = [
            dimension
            for dimension in dimensions
            if dimension is not None
        ]

        return AIMatchContext(
            match_id=match.id,
            score=match.score,
            dimensions=applicable_dimensions,
            matching_version=match.matching_version,
        )

    # ========================================================
    # DIMENSION
    # ========================================================

    @staticmethod
    def _make_dimension(
            *,
            name: str,
            score: Decimal | None,
            contribution: Decimal | None,
    ) -> AIMatchDimension | None:
        """
        Convert one persisted Match dimension into AI context.

        None means the dimension was not applicable and should
        not be presented to the AI as a mismatch.
        """

        if score is None:
            return None

        return AIMatchDimension(
            dimension=name,
            score=score,
            contribution=contribution,
        )

    # ========================================================
    # GENERATE INTRODUCTION
    # ========================================================

    def generate_introduction(
            self,
            *,
            conversation_id: UUID,
            user_id: UUID,
            request: AIIntroductionRequest,
    ) -> AIIntroductionResponse:

        context = self.build_introduction_context(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        try:
            result = self.llm.generate_introduction(
                context=context,
                instruction=request.instruction,
            )

        except AIIntroductionGenerationError as exc:
            self._record_failed_generation(
                context=context,
                user_id=user_id,
                error_code=exc.error_code,
            )

            # The failed generation is observability data.
            # It must survive the generation error.
            self.session.commit()

            raise

        self.repository.create_generation(
            user_id=user_id,
            conversation_id=context.conversation_id,
            match_id=context.match.match_id,

            model=result.metadata.model,
            prompt_version=result.metadata.prompt_version,

            latency_ms=result.metadata.latency_ms,
            input_tokens=result.metadata.input_tokens,
            output_tokens=result.metadata.output_tokens,

            generated_message=result.introduction.message,

            success=True,
        )

        return AIIntroductionResponse(
            suggestion=result.introduction.message,
        )

    # ========================================================
    # FAILED GENERATION
    # ========================================================

    def _record_failed_generation(
            self,
            *,
            context: AIIntroductionContext,
            user_id: UUID,
            error_code: str,
    ) -> None:
        """
        Persist controlled observability information for a
        failed LLM generation.

        Provider exception text is deliberately not stored.
        """

        self.repository.create_generation(
            user_id=user_id,
            conversation_id=context.conversation_id,
            match_id=context.match.match_id,

            model=self.llm.model,
            prompt_version=self.llm.prompt.version,

            success=False,
            error_code=error_code,
        )
