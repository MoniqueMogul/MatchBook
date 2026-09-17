from app.db.db_enum import MatchStatus, EventType
from app.db.db_model import (
    Business,
    BuyerPreferences,
)
from decimal import Decimal
from uuid import UUID

from app.db.db_model import Match
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate
from app.matching.config import (
    DEFAULT_MIN_FIT_THRESHOLD,
    MATCHING_VERSION,
)
from app.matching.repository import MatchingRepository
from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
    MatchEvaluation,
    RankedMatch,
)
from app.matching.scoring import score_candidate


# ============================================================
# ORM -> MATCHING INPUT
# ============================================================


def build_buyer_match_input(
    preferences: BuyerPreferences,
) -> BuyerMatchInput:
    """
    Convert persisted BuyerPreferences into the clean input
    expected by the deterministic scoring engine.
    """

    return BuyerMatchInput(
        buyer_id=preferences.buyer_id,

        target_industries=preferences.target_industries,
        target_locations=preferences.target_locations,
        maximum_purchase_price=(
            preferences.maximum_purchase_price
        ),

        minimum_sde=preferences.minimum_required_sde,
        preferred_sde=preferences.preferred_sde,

        minimum_arr=preferences.minimum_required_arr,
        preferred_arr=preferences.preferred_arr,

        preferred_owner_hours=(
            preferences.preferred_owner_hours_per_week
        ),

        required_training_days=(
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
    )


def build_business_match_input(
    business: Business,
) -> BusinessMatchInput:
    """
    Convert a persisted Business into the clean input expected
    by the deterministic scoring engine.
    """

    return BusinessMatchInput(
        business_id=business.id,

        industry=business.industry,
        state=business.state,
        city=business.city,
        county=business.county,
        asking_price=business.asking_price,

        sde=business.sde,
        arr=business.arr,

        owner_hours=(
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
    )


# ============================================================
# SCORE CANDIDATES
# ============================================================


def score_business_candidates(
    *,
    buyer: BuyerMatchInput,
    businesses: list[Business],
) -> list[MatchEvaluation]:
    """
    Score businesses that have already passed DB hard filters.
    """

    evaluations = []

    for business in businesses:
        business_input = build_business_match_input(
            business
        )

        evaluation = score_candidate(
            buyer=buyer,
            business=business_input,
        )

        evaluations.append(evaluation)

    return evaluations


# ============================================================
# THRESHOLD + RANK
# ============================================================


def rank_evaluations(
    evaluations: list[MatchEvaluation],
    *,
    threshold: float = DEFAULT_MIN_FIT_THRESHOLD,
) -> list[RankedMatch]:
    """
    Keep every qualifying match and rank strongest first.

    Top-N / pagination is a retrieval concern, not a
    persistence concern.
    """

    qualified = [
        evaluation
        for evaluation in evaluations
        if evaluation.score >= threshold
    ]

    qualified.sort(
        key=lambda evaluation: evaluation.score,
        reverse=True,
    )

    return [
        RankedMatch(
            rank=rank,
            evaluation=evaluation,
        )
        for rank, evaluation in enumerate(
            qualified,
            start=1,
        )
    ]

# ============================================================
# BUYER MATCHING
# ============================================================


def evaluate_buyer_matches(
    repository: MatchingRepository,
    buyer_id: UUID,
    *,
    threshold: float = DEFAULT_MIN_FIT_THRESHOLD,
) -> list[RankedMatch]:

    preferences = repository.require_buyer_preferences(
        buyer_id
    )

    buyer_input = build_buyer_match_input(
        preferences
    )

    excluded_business_ids = (
        repository.get_non_rerankable_business_ids_for_buyer(
            buyer_id
        )
    )

    candidate_businesses = (
        repository.get_candidate_businesses(
            preferences,
            excluded_business_ids=excluded_business_ids,
        )
    )

    evaluations = score_business_candidates(
        buyer=buyer_input,
        businesses=candidate_businesses,
    )

    return rank_evaluations(
        evaluations,
        threshold=threshold,
    )

# ============================================================
# MATCH PERSISTENCE
# ============================================================


def persist_evaluation(
    *,
    repository: MatchingRepository,
    evaluation: MatchEvaluation,
) -> tuple[Match, bool]:
    """
    Persist a qualifying match evaluation.

    Returns:
        (match, created)

    created=True means a brand-new Match was created.
    created=False means an existing Match was updated or preserved.
    """

    existing = repository.get_match(
        buyer_id=evaluation.buyer_id,
        business_id=evaluation.business_id,
    )

    # Matching does not own relationships that have moved
    # beyond the recommendation stage.
    if (
        existing is not None
        and existing.status != MatchStatus.MATCHED
    ):
        return existing, False

    def score(name: str) -> Decimal | None:
        dimension = evaluation.dimensions.get(name)

        if dimension is None:
            return None

        return Decimal(str(dimension.score))

    def contribution(name: str) -> Decimal | None:
        dimension = evaluation.dimensions.get(name)

        if dimension is None:
            return None

        return Decimal(str(dimension.contribution))

    values = {
        "score": Decimal(str(evaluation.score)),

        # Industry and geography are hard filters,
        # not scoring dimensions.
        "industry_score": None,
        "geography_score": None,

        "price_score": score("purchase_price"),
        "sde_score": score("sde"),
        "arr_score": score("arr"),
        "owner_involvement_score": score("owner_involvement"),
        "customer_concentration_score": score(
            "customer_concentration"
        ),
        "transition_training_score": score(
            "transition_training"
        ),
        "deal_preference_score": score("deal_preference"),

        "industry_contribution": None,
        "geography_contribution": None,

        "price_contribution": contribution("purchase_price"),
        "sde_contribution": contribution("sde"),
        "arr_contribution": contribution("arr"),
        "owner_involvement_contribution": contribution(
            "owner_involvement"
        ),
        "customer_concentration_contribution": contribution(
            "customer_concentration"
        ),
        "transition_training_contribution": contribution(
            "transition_training"
        ),
        "deal_preference_contribution": contribution(
            "deal_preference"
        ),

        "score_breakdown": {
            name: dimension.model_dump()
            for name, dimension in evaluation.dimensions.items()
        },

        "matching_version": MATCHING_VERSION,
    }

    # Brand-new recommendation.
    if existing is None:
        match = Match(
            buyer_id=evaluation.buyer_id,
            business_id=evaluation.business_id,
            status=MatchStatus.MATCHED,
            **values,
        )

        match = repository.add_match(match)

        return match, True

    # Existing MATCHED recommendation: just rescore it.
    for field, value in values.items():
        setattr(existing, field, value)

    return existing, False


# ============================================================
# MATCH BUYER
# ============================================================


def match_buyer(
    *,
    repository: MatchingRepository,
    buyer_id: UUID,
    threshold: float = DEFAULT_MIN_FIT_THRESHOLD,
) -> list[RankedMatch]:
    """
    Recalculate all currently qualifying recommendations
    for a buyer.
    """

    ranked_matches = evaluate_buyer_matches(
        repository=repository,
        buyer_id=buyer_id,
        threshold=threshold,
    )

    remove_displaced_recommendations(
        repository=repository,
        buyer_id=buyer_id,
        ranked_matches=ranked_matches,
    )

    outbox_repository = OutboxRepository(
        repository.session
    )

    for ranked_match in ranked_matches:
        match, created = persist_evaluation(
            repository=repository,
            evaluation=ranked_match.evaluation,
        )

        if created:
            stage_match_created_event(
                outbox_repository=outbox_repository,
                match=match,
            )

    return ranked_matches


# ============================================================
# MATCH BUSINESS
# ============================================================


def match_business(
    *,
    repository: MatchingRepository,
    business_id: UUID,
    threshold: float = DEFAULT_MIN_FIT_THRESHOLD,
) -> dict[UUID, list[RankedMatch]]:
    """
    Recalculate affected buyers when a business changes.

    The business is used only to discover which buyers may
    be affected. Each buyer is then recalculated normally,
    preserving buyer-level Top-N semantics.
    """

    business = repository.require_business(
        business_id
    )

    candidate_buyers = repository.get_candidate_buyers(
        business
    )

    results: dict[UUID, list[RankedMatch]] = {}

    for preferences in candidate_buyers:
        ranked_matches = match_buyer(
            repository=repository,
            buyer_id=preferences.buyer_id,
            threshold=threshold,
        )

        results[preferences.buyer_id] = ranked_matches

    return results


def remove_displaced_recommendations(
    *,
    repository: MatchingRepository,
    buyer_id: UUID,
    ranked_matches: list[RankedMatch],
) -> None:
    """
    Remove old MATCHED recommendations that are no longer
    part of the buyer's current Top-N.

    INTERESTED and later lifecycle matches are untouched.
    REJECTED matches are untouched.
    """

    current_business_ids = {
        ranked_match.evaluation.business_id
        for ranked_match in ranked_matches
    }

    existing_matches = (
        repository.list_rerankable_matches_for_buyer(
            buyer_id
        )
    )

    for match in existing_matches:
        if match.business_id not in current_business_ids:
            repository.delete_match(match)


def stage_match_created_event(
    *,
    outbox_repository: OutboxRepository,
    match: Match,
) -> None:
    """
    Stage MATCH_CREATED in the transactional outbox.
    """

    outbox_repository.create_event(
        OutboxEventCreate(
            idempotency_key=f"match-created:{match.id}",
            event_type=EventType.MATCH_CREATED,
            entity_type="match",
            entity_id=match.id,
            payload={
                "match_id": str(match.id),
                "buyer_id": str(match.buyer_id),
                "business_id": str(match.business_id),
            },
        )
    )