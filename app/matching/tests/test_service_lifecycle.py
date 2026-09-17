from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.db.db_enum import MatchStatus, EventType
from app.db.db_model import Match
from app.matching.config import MATCHING_VERSION
from app.matching.schemas import (
    DimensionScore,
    MatchEvaluation,
    RankedMatch,
)

from app.matching.service import (
    persist_evaluation,
    remove_displaced_recommendations,
    match_buyer, match_business, stage_match_created_event,
)


# ============================================================
# HELPERS
# ============================================================


def make_dimension(
    *,
    score: float,
    weight: float,
) -> DimensionScore:
    return DimensionScore(
        score=score,
        weight=weight,
        contribution=score * weight,
    )


def make_evaluation(
    *,
    buyer_id=None,
    business_id=None,
    score=0.85,
) -> MatchEvaluation:
    return MatchEvaluation(
        buyer_id=buyer_id or uuid4(),
        business_id=business_id or uuid4(),
        score=score,
        dimensions={
            "purchase_price": make_dimension(
                score=0.90,
                weight=0.30,
            ),
            "sde": make_dimension(
                score=0.80,
                weight=0.30,
            ),
            "arr": make_dimension(
                score=0.70,
                weight=0.05,
            ),
            "owner_involvement": make_dimension(
                score=1.00,
                weight=0.10,
            ),
            "transition_training": make_dimension(
                score=0.80,
                weight=0.10,
            ),
            "deal_preference": make_dimension(
                score=1.00,
                weight=0.10,
            ),
            "customer_concentration": make_dimension(
                score=1.00,
                weight=0.05,
            ),
        },
    )


def make_existing_match(
    evaluation: MatchEvaluation,
    *,
    status: MatchStatus,
    score: Decimal = Decimal("0.5000"),
) -> Match:
    return Match(
        id=uuid4(),
        buyer_id=evaluation.buyer_id,
        business_id=evaluation.business_id,
        score=score,
        status=status,
        matching_version="old-version",
    )


# ============================================================
# CREATE
# ============================================================


def test_persist_evaluation_creates_new_matched_relationship():
    repository = Mock()

    evaluation = make_evaluation()

    repository.get_match.return_value = None

    repository.add_match.side_effect = (
        lambda match: match
    )

    match, created = persist_evaluation(
        repository=repository,
        evaluation=evaluation,
    )

    assert created is True

    assert match.buyer_id == evaluation.buyer_id
    assert match.business_id == evaluation.business_id

    assert match.status == MatchStatus.MATCHED

    assert match.score == Decimal("0.85")

    assert match.matching_version == MATCHING_VERSION

    repository.add_match.assert_called_once_with(
        match
    )


def test_new_match_persists_dimension_scores():
    repository = Mock()

    evaluation = make_evaluation()

    repository.get_match.return_value = None

    repository.add_match.side_effect = (
        lambda match: match
    )

    match, _ = persist_evaluation(
        repository=repository,
        evaluation=evaluation,
    )

    assert match.price_score == Decimal("0.9")
    assert match.sde_score == Decimal("0.8")
    assert match.arr_score == Decimal("0.7")

    assert (
        match.owner_involvement_score
        == Decimal("1.0")
    )

    assert (
        match.transition_training_score
        == Decimal("0.8")
    )

    assert (
        match.deal_preference_score
        == Decimal("1.0")
    )

    assert (
        match.customer_concentration_score
        == Decimal("1.0")
    )


def test_new_match_does_not_store_hard_filters_as_scores():
    repository = Mock()

    evaluation = make_evaluation()

    repository.get_match.return_value = None

    repository.add_match.side_effect = (
        lambda match: match
    )

    match, _ = persist_evaluation(
        repository=repository,
        evaluation=evaluation,
    )

    assert match.industry_score is None
    assert match.geography_score is None

    assert match.industry_contribution is None
    assert match.geography_contribution is None


# ============================================================
# RESCORE EXISTING MATCHED
# ============================================================


def test_existing_matched_relationship_is_rescored():
    repository = Mock()

    evaluation = make_evaluation(
        score=0.91
    )

    existing = make_existing_match(
        evaluation,
        status=MatchStatus.MATCHED,
        score=Decimal("0.40"),
    )

    repository.get_match.return_value = existing

    match, created = persist_evaluation(
        repository=repository,
        evaluation=evaluation,
    )

    assert created is False

    assert match is existing

    assert match.status == MatchStatus.MATCHED

    assert match.score == Decimal("0.91")

    assert match.matching_version == MATCHING_VERSION

    repository.add_match.assert_not_called()


def test_rescore_replaces_old_score_breakdown():
    repository = Mock()

    evaluation = make_evaluation(
        score=0.91
    )

    existing = make_existing_match(
        evaluation,
        status=MatchStatus.MATCHED,
    )

    existing.score_breakdown = {
        "old": {
            "score": 0.1,
        }
    }

    repository.get_match.return_value = existing

    match, _ = persist_evaluation(
        repository=repository,
        evaluation=evaluation,
    )

    assert "old" not in match.score_breakdown

    assert "purchase_price" in match.score_breakdown
    assert "sde" in match.score_breakdown
    assert "arr" in match.score_breakdown


# ============================================================
# PROTECTED RELATIONSHIP LIFECYCLE
# ============================================================


@pytest.mark.parametrize(
    "status",
    [
        MatchStatus.INTERESTED,
        MatchStatus.VERIFICATION,
        MatchStatus.NDA,
        MatchStatus.DUE_DILIGENCE,
        MatchStatus.OFFER,
        MatchStatus.LOI,
        MatchStatus.FINANCING,
        MatchStatus.CLOSING,
        MatchStatus.COMPLETED,
        MatchStatus.REJECTED,
        MatchStatus.EXPIRED,
    ],
)
def test_non_matched_relationship_is_never_overwritten(
    status,
):
    repository = Mock()

    evaluation = make_evaluation(
        score=0.99
    )

    existing = make_existing_match(
        evaluation,
        status=status,
        score=Decimal("0.42"),
    )

    original_score = existing.score
    original_version = existing.matching_version

    repository.get_match.return_value = existing

    match, created = persist_evaluation(
        repository=repository,
        evaluation=evaluation,
    )

    assert created is False

    assert match is existing

    assert match.status == status

    assert match.score == original_score

    assert (
        match.matching_version
        == original_version
    )

    repository.add_match.assert_not_called()


# ============================================================
# DUPLICATE PROTECTION
# ============================================================


def test_existing_match_does_not_create_duplicate():
    repository = Mock()

    evaluation = make_evaluation()

    existing = make_existing_match(
        evaluation,
        status=MatchStatus.MATCHED,
    )

    repository.get_match.return_value = existing

    first_match, first_created = persist_evaluation(
        repository=repository,
        evaluation=evaluation,
    )

    second_match, second_created = persist_evaluation(
        repository=repository,
        evaluation=evaluation,
    )

    assert first_created is False
    assert second_created is False

    assert first_match is existing
    assert second_match is existing

    repository.add_match.assert_not_called()


# ============================================================
# REMOVE DISPLACED RECOMMENDATIONS
# ============================================================


def make_ranked_match(
    *,
    buyer_id,
    business_id,
    score=0.85,
    rank=1,
) -> RankedMatch:
    evaluation = make_evaluation(
        buyer_id=buyer_id,
        business_id=business_id,
        score=score,
    )

    return RankedMatch(
        rank=rank,
        evaluation=evaluation,
    )


def test_displaced_matched_recommendation_is_removed():
    repository = Mock()

    buyer_id = uuid4()

    kept_business_id = uuid4()
    displaced_business_id = uuid4()

    kept_match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=kept_business_id,
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    displaced_match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=displaced_business_id,
        score=Decimal("0.80"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    repository.list_rerankable_matches_for_buyer.return_value = [
        kept_match,
        displaced_match,
    ]

    ranked_matches = [
        make_ranked_match(
            buyer_id=buyer_id,
            business_id=kept_business_id,
        )
    ]

    remove_displaced_recommendations(
        repository=repository,
        buyer_id=buyer_id,
        ranked_matches=ranked_matches,
    )

    repository.delete_match.assert_called_once_with(
        displaced_match
    )


def test_current_matched_recommendation_is_not_removed():
    repository = Mock()

    buyer_id = uuid4()
    business_id = uuid4()

    existing = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=business_id,
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    repository.list_rerankable_matches_for_buyer.return_value = [
        existing
    ]

    ranked_matches = [
        make_ranked_match(
            buyer_id=buyer_id,
            business_id=business_id,
        )
    ]

    remove_displaced_recommendations(
        repository=repository,
        buyer_id=buyer_id,
        ranked_matches=ranked_matches,
    )

    repository.delete_match.assert_not_called()


def test_empty_new_results_remove_all_old_matched_recommendations():
    repository = Mock()

    buyer_id = uuid4()

    first_match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=uuid4(),
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    second_match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=uuid4(),
        score=Decimal("0.75"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    repository.list_rerankable_matches_for_buyer.return_value = [
        first_match,
        second_match,
    ]

    remove_displaced_recommendations(
        repository=repository,
        buyer_id=buyer_id,
        ranked_matches=[],
    )

    assert repository.delete_match.call_count == 2

    repository.delete_match.assert_any_call(
        first_match
    )

    repository.delete_match.assert_any_call(
        second_match
    )


def test_only_rerankable_matches_are_requested_for_removal():
    repository = Mock()

    buyer_id = uuid4()

    repository.list_rerankable_matches_for_buyer.return_value = []

    remove_displaced_recommendations(
        repository=repository,
        buyer_id=buyer_id,
        ranked_matches=[],
    )

    repository.list_rerankable_matches_for_buyer.assert_called_once_with(
        buyer_id
    )

    repository.delete_match.assert_not_called()


def test_multiple_current_recommendations_are_all_preserved():
    repository = Mock()

    buyer_id = uuid4()

    business_1 = uuid4()
    business_2 = uuid4()
    business_3 = uuid4()

    existing_matches = [
        Match(
            id=uuid4(),
            buyer_id=buyer_id,
            business_id=business_id,
            score=Decimal("0.80"),
            status=MatchStatus.MATCHED,
            matching_version=MATCHING_VERSION,
        )
        for business_id in [
            business_1,
            business_2,
            business_3,
        ]
    ]

    repository.list_rerankable_matches_for_buyer.return_value = (
        existing_matches
    )

    ranked_matches = [
        make_ranked_match(
            buyer_id=buyer_id,
            business_id=business_1,
            rank=1,
        ),
        make_ranked_match(
            buyer_id=buyer_id,
            business_id=business_2,
            rank=2,
        ),
        make_ranked_match(
            buyer_id=buyer_id,
            business_id=business_3,
            rank=3,
        ),
    ]

    remove_displaced_recommendations(
        repository=repository,
        buyer_id=buyer_id,
        ranked_matches=ranked_matches,
    )

    repository.delete_match.assert_not_called()


# ============================================================
# MATCH BUYER ORCHESTRATION
# ============================================================


@patch("app.matching.service.stage_match_created_event")
@patch("app.matching.service.OutboxRepository")
@patch("app.matching.service.persist_evaluation")
@patch("app.matching.service.remove_displaced_recommendations")
@patch("app.matching.service.evaluate_buyer_matches")
def test_match_buyer_runs_full_flow_in_correct_order(
    mock_evaluate,
    mock_remove,
    mock_persist,
    mock_outbox_class,
    mock_stage_event,
):
    repository = Mock()
    repository.session = Mock()

    buyer_id = uuid4()
    business_id = uuid4()

    ranked = make_ranked_match(
        buyer_id=buyer_id,
        business_id=business_id,
    )

    mock_evaluate.return_value = [ranked]

    match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=business_id,
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    mock_persist.return_value = (
        match,
        True,
    )

    outbox_repository = Mock()
    mock_outbox_class.return_value = outbox_repository

    result = match_buyer(
        repository=repository,
        buyer_id=buyer_id,
        threshold=0.70,
    )

    assert result == [ranked]

    mock_evaluate.assert_called_once_with(
        repository=repository,
        buyer_id=buyer_id,
        threshold=0.70,
    )

    mock_remove.assert_called_once_with(
        repository=repository,
        buyer_id=buyer_id,
        ranked_matches=[ranked],
    )

    mock_persist.assert_called_once_with(
        repository=repository,
        evaluation=ranked.evaluation,
    )

    mock_outbox_class.assert_called_once_with(
        repository.session
    )

    mock_stage_event.assert_called_once_with(
        outbox_repository=outbox_repository,
        match=match,
    )


@patch("app.matching.service.stage_match_created_event")
@patch("app.matching.service.OutboxRepository")
@patch("app.matching.service.persist_evaluation")
@patch("app.matching.service.remove_displaced_recommendations")
@patch("app.matching.service.evaluate_buyer_matches")
def test_new_match_stages_match_created_event(
    mock_evaluate,
    mock_remove,
    mock_persist,
    mock_outbox_class,
    mock_stage_event,
):
    repository = Mock()
    repository.session = Mock()

    buyer_id = uuid4()
    business_id = uuid4()

    ranked = make_ranked_match(
        buyer_id=buyer_id,
        business_id=business_id,
    )

    mock_evaluate.return_value = [ranked]

    match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=business_id,
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    mock_persist.return_value = (
        match,
        True,
    )

    outbox_repository = Mock()
    mock_outbox_class.return_value = outbox_repository

    match_buyer(
        repository=repository,
        buyer_id=buyer_id,
    )

    mock_stage_event.assert_called_once_with(
        outbox_repository=outbox_repository,
        match=match,
    )


@patch("app.matching.service.stage_match_created_event")
@patch("app.matching.service.OutboxRepository")
@patch("app.matching.service.persist_evaluation")
@patch("app.matching.service.remove_displaced_recommendations")
@patch("app.matching.service.evaluate_buyer_matches")
def test_existing_match_does_not_stage_match_created_event(
    mock_evaluate,
    mock_remove,
    mock_persist,
    mock_outbox_class,
    mock_stage_event,
):
    repository = Mock()
    repository.session = Mock()

    buyer_id = uuid4()
    business_id = uuid4()

    ranked = make_ranked_match(
        buyer_id=buyer_id,
        business_id=business_id,
    )

    mock_evaluate.return_value = [ranked]

    existing_match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=business_id,
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    mock_persist.return_value = (
        existing_match,
        False,
    )

    match_buyer(
        repository=repository,
        buyer_id=buyer_id,
    )

    mock_stage_event.assert_not_called()


@patch("app.matching.service.stage_match_created_event")
@patch("app.matching.service.OutboxRepository")
@patch("app.matching.service.persist_evaluation")
@patch("app.matching.service.remove_displaced_recommendations")
@patch("app.matching.service.evaluate_buyer_matches")
def test_empty_results_remove_stale_recommendations_but_persist_nothing(
    mock_evaluate,
    mock_remove,
    mock_persist,
    mock_outbox_class,
    mock_stage_event,
):
    repository = Mock()
    repository.session = Mock()

    buyer_id = uuid4()

    mock_evaluate.return_value = []

    result = match_buyer(
        repository=repository,
        buyer_id=buyer_id,
    )

    assert result == []

    mock_remove.assert_called_once_with(
        repository=repository,
        buyer_id=buyer_id,
        ranked_matches=[],
    )

    mock_persist.assert_not_called()
    mock_stage_event.assert_not_called()


@patch("app.matching.service.stage_match_created_event")
@patch("app.matching.service.OutboxRepository")
@patch("app.matching.service.persist_evaluation")
@patch("app.matching.service.remove_displaced_recommendations")
@patch("app.matching.service.evaluate_buyer_matches")
def test_multiple_new_matches_each_stage_one_event(
    mock_evaluate,
    mock_remove,
    mock_persist,
    mock_outbox_class,
    mock_stage_event,
):
    repository = Mock()
    repository.session = Mock()

    buyer_id = uuid4()

    ranked_1 = make_ranked_match(
        buyer_id=buyer_id,
        business_id=uuid4(),
        rank=1,
        score=0.90,
    )

    ranked_2 = make_ranked_match(
        buyer_id=buyer_id,
        business_id=uuid4(),
        rank=2,
        score=0.80,
    )

    mock_evaluate.return_value = [
        ranked_1,
        ranked_2,
    ]

    match_1 = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=ranked_1.evaluation.business_id,
        score=Decimal("0.90"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    match_2 = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=ranked_2.evaluation.business_id,
        score=Decimal("0.80"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    mock_persist.side_effect = [
        (match_1, True),
        (match_2, True),
    ]

    outbox_repository = Mock()
    mock_outbox_class.return_value = outbox_repository

    result = match_buyer(
        repository=repository,
        buyer_id=buyer_id,
    )

    assert result == [
        ranked_1,
        ranked_2,
    ]

    assert mock_persist.call_count == 2
    assert mock_stage_event.call_count == 2

    mock_stage_event.assert_any_call(
        outbox_repository=outbox_repository,
        match=match_1,
    )

    mock_stage_event.assert_any_call(
        outbox_repository=outbox_repository,
        match=match_2,
    )


@patch("app.matching.service.stage_match_created_event")
@patch("app.matching.service.OutboxRepository")
@patch("app.matching.service.persist_evaluation")
@patch("app.matching.service.remove_displaced_recommendations")
@patch("app.matching.service.evaluate_buyer_matches")
def test_only_new_matches_stage_events_when_results_are_mixed(
    mock_evaluate,
    mock_remove,
    mock_persist,
    mock_outbox_class,
    mock_stage_event,
):
    repository = Mock()
    repository.session = Mock()

    buyer_id = uuid4()

    ranked_existing = make_ranked_match(
        buyer_id=buyer_id,
        business_id=uuid4(),
        rank=1,
    )

    ranked_new = make_ranked_match(
        buyer_id=buyer_id,
        business_id=uuid4(),
        rank=2,
    )

    mock_evaluate.return_value = [
        ranked_existing,
        ranked_new,
    ]

    existing_match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=ranked_existing.evaluation.business_id,
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    new_match = Match(
        id=uuid4(),
        buyer_id=buyer_id,
        business_id=ranked_new.evaluation.business_id,
        score=Decimal("0.80"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    mock_persist.side_effect = [
        (existing_match, False),
        (new_match, True),
    ]

    outbox_repository = Mock()
    mock_outbox_class.return_value = outbox_repository

    match_buyer(
        repository=repository,
        buyer_id=buyer_id,
    )

    mock_stage_event.assert_called_once_with(
        outbox_repository=outbox_repository,
        match=new_match,
    )


# ============================================================
# MATCH BUSINESS ORCHESTRATION
# ============================================================


@patch("app.matching.service.match_buyer")
def test_match_business_recalculates_each_candidate_buyer(
    mock_match_buyer,
):
    repository = Mock()

    business_id = uuid4()

    business = Mock()
    business.id = business_id

    buyer_1 = Mock()
    buyer_1.buyer_id = uuid4()

    buyer_2 = Mock()
    buyer_2.buyer_id = uuid4()

    repository.require_business.return_value = business
    repository.get_candidate_buyers.return_value = [
        buyer_1,
        buyer_2,
    ]

    buyer_1_results = [
        make_ranked_match(
            buyer_id=buyer_1.buyer_id,
            business_id=business_id,
        )
    ]

    buyer_2_results = [
        make_ranked_match(
            buyer_id=buyer_2.buyer_id,
            business_id=business_id,
        )
    ]

    mock_match_buyer.side_effect = [
        buyer_1_results,
        buyer_2_results,
    ]

    result = match_business(
        repository=repository,
        business_id=business_id,
        threshold=0.70,
    )

    repository.require_business.assert_called_once_with(
        business_id
    )

    repository.get_candidate_buyers.assert_called_once_with(
        business
    )

    assert mock_match_buyer.call_count == 2

    mock_match_buyer.assert_any_call(
        repository=repository,
        buyer_id=buyer_1.buyer_id,
        threshold=0.70,
    )

    mock_match_buyer.assert_any_call(
        repository=repository,
        buyer_id=buyer_2.buyer_id,
        threshold=0.70,
    )

    assert result == {
        buyer_1.buyer_id: buyer_1_results,
        buyer_2.buyer_id: buyer_2_results,
    }


@patch("app.matching.service.match_buyer")
def test_match_business_with_no_candidate_buyers_does_nothing(
    mock_match_buyer,
):
    repository = Mock()

    business_id = uuid4()

    business = Mock()
    business.id = business_id

    repository.require_business.return_value = business
    repository.get_candidate_buyers.return_value = []

    result = match_business(
        repository=repository,
        business_id=business_id,
    )

    assert result == {}

    mock_match_buyer.assert_not_called()


@patch("app.matching.service.match_buyer")
def test_match_business_passes_threshold_to_every_buyer(
    mock_match_buyer,
):
    repository = Mock()

    business_id = uuid4()

    business = Mock()
    business.id = business_id

    buyer = Mock()
    buyer.buyer_id = uuid4()

    repository.require_business.return_value = business
    repository.get_candidate_buyers.return_value = [
        buyer
    ]

    mock_match_buyer.return_value = []

    match_business(
        repository=repository,
        business_id=business_id,
        threshold=0.82,
    )

    mock_match_buyer.assert_called_once_with(
        repository=repository,
        buyer_id=buyer.buyer_id,
        threshold=0.82,
    )

# ============================================================
# MATCH CREATED OUTBOX EVENT
# ============================================================


def test_stage_match_created_event_creates_correct_event():
    outbox_repository = Mock()

    buyer_id = uuid4()
    business_id = uuid4()
    match_id = uuid4()

    match = Match(
        id=match_id,
        buyer_id=buyer_id,
        business_id=business_id,
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    stage_match_created_event(
        outbox_repository=outbox_repository,
        match=match,
    )

    outbox_repository.create_event.assert_called_once()

    event = (
        outbox_repository
        .create_event
        .call_args
        .args[0]
    )

    assert event.event_type == EventType.MATCH_CREATED

    assert event.entity_type == "match"

    assert event.entity_id == match_id


def test_match_created_event_contains_correct_payload():
    outbox_repository = Mock()

    buyer_id = uuid4()
    business_id = uuid4()
    match_id = uuid4()

    match = Match(
        id=match_id,
        buyer_id=buyer_id,
        business_id=business_id,
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    stage_match_created_event(
        outbox_repository=outbox_repository,
        match=match,
    )

    event = (
        outbox_repository
        .create_event
        .call_args
        .args[0]
    )

    assert event.payload == {
        "match_id": str(match_id),
        "buyer_id": str(buyer_id),
        "business_id": str(business_id),
    }


def test_match_created_event_uses_match_id_for_idempotency_key():
    outbox_repository = Mock()

    match_id = uuid4()

    match = Match(
        id=match_id,
        buyer_id=uuid4(),
        business_id=uuid4(),
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    stage_match_created_event(
        outbox_repository=outbox_repository,
        match=match,
    )

    event = (
        outbox_repository
        .create_event
        .call_args
        .args[0]
    )

    assert (
        event.idempotency_key
        == f"match-created:{match_id}"
    )


def test_same_match_always_generates_same_idempotency_key():
    outbox_repository = Mock()

    match = Match(
        id=uuid4(),
        buyer_id=uuid4(),
        business_id=uuid4(),
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    stage_match_created_event(
        outbox_repository=outbox_repository,
        match=match,
    )

    stage_match_created_event(
        outbox_repository=outbox_repository,
        match=match,
    )

    assert outbox_repository.create_event.call_count == 2

    first_event = (
        outbox_repository
        .create_event
        .call_args_list[0]
        .args[0]
    )

    second_event = (
        outbox_repository
        .create_event
        .call_args_list[1]
        .args[0]
    )

    assert (
        first_event.idempotency_key
        == second_event.idempotency_key
    )

    assert (
        first_event.idempotency_key
        == f"match-created:{match.id}"
    )


def test_different_matches_generate_different_idempotency_keys():
    outbox_repository = Mock()

    first_match = Match(
        id=uuid4(),
        buyer_id=uuid4(),
        business_id=uuid4(),
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    second_match = Match(
        id=uuid4(),
        buyer_id=uuid4(),
        business_id=uuid4(),
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    stage_match_created_event(
        outbox_repository=outbox_repository,
        match=first_match,
    )

    stage_match_created_event(
        outbox_repository=outbox_repository,
        match=second_match,
    )

    first_event = (
        outbox_repository
        .create_event
        .call_args_list[0]
        .args[0]
    )

    second_event = (
        outbox_repository
        .create_event
        .call_args_list[1]
        .args[0]
    )

    assert (
        first_event.idempotency_key
        != second_event.idempotency_key
    )


def test_match_created_event_payload_uses_strings_for_uuid_values():
    outbox_repository = Mock()

    match = Match(
        id=uuid4(),
        buyer_id=uuid4(),
        business_id=uuid4(),
        score=Decimal("0.85"),
        status=MatchStatus.MATCHED,
        matching_version=MATCHING_VERSION,
    )

    stage_match_created_event(
        outbox_repository=outbox_repository,
        match=match,
    )

    event = (
        outbox_repository
        .create_event
        .call_args
        .args[0]
    )

    assert isinstance(
        event.payload["match_id"],
        str,
    )

    assert isinstance(
        event.payload["buyer_id"],
        str,
    )

    assert isinstance(
        event.payload["business_id"],
        str,
    )