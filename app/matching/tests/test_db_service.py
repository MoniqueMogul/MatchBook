from decimal import Decimal
from unittest.mock import (
    Mock,
    patch,
)
from uuid import uuid4

import pytest

from app.matching.db_service import (
    MatchingDatabaseServiceError,
    _build_candidate_inputs,
    recalculate_matches_for_buyer,
)

from app.matching.repository import (
    MatchingDataIncompleteError,
)

from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
    DimensionScore,
    MatchEvaluation,
    RankedMatch,
)


# ============================================================
# TEST DATA
# ============================================================


def make_buyer_input(
    *,
    buyer_id=None,
) -> BuyerMatchInput:
    return BuyerMatchInput(
        buyer_id=(
            buyer_id
            or uuid4()
        ),

        target_industries=[
            "HVAC",
        ],

        target_locations={
            "state": "Florida",
        },

        maximum_purchase_price=Decimal(
            "500000"
        ),

        minimum_sde=Decimal(
            "100000"
        ),

        preferred_sde=Decimal(
            "200000"
        ),

        preferred_owner_hours=20.0,

        required_training_days=30.0,

        deal_preference="cash",

        minimum_arr=Decimal(
            "200000"
        ),

        preferred_arr=Decimal(
            "500000"
        ),

        accepts_customer_concentration_above_25_percent=False,

        minimum_years_in_operation=3,
    )


def make_business_input(
    *,
    business_id=None,
) -> BusinessMatchInput:
    return BusinessMatchInput(
        business_id=(
            business_id
            or uuid4()
        ),

        industry="HVAC",

        city="Orlando",

        county="Orange",

        state="Florida",

        asking_price=Decimal(
            "500000"
        ),

        sde=Decimal(
            "200000"
        ),

        owner_hours=20.0,

        transition_training_days=30.0,

        deal_preference="cash",

        arr=Decimal(
            "500000"
        ),

        largest_customer_percent=20.0,

        years_in_operation=10,
    )


def make_evaluation(
    *,
    buyer_id=None,
    business_id=None,
) -> MatchEvaluation:
    return MatchEvaluation(
        buyer_id=(
            buyer_id
            or uuid4()
        ),

        business_id=(
            business_id
            or uuid4()
        ),

        eligible=True,

        failed_constraints=[],

        score=1.0,

        percentage=100.0,

        dimensions={
            "industry": DimensionScore(
                score=1.0,
                weight=0.0,
                contribution=0.0,
            ),

            "geography": DimensionScore(
                score=1.0,
                weight=0.0,
                contribution=0.0,
            ),

            "purchase_price": DimensionScore(
                score=1.0,
                weight=0.30,
                contribution=0.30,
            ),

            "sde": DimensionScore(
                score=1.0,
                weight=0.30,
                contribution=0.30,
            ),

            "owner_involvement": DimensionScore(
                score=1.0,
                weight=0.10,
                contribution=0.10,
            ),

            "transition_training": DimensionScore(
                score=1.0,
                weight=0.10,
                contribution=0.10,
            ),

            "deal_preference": DimensionScore(
                score=1.0,
                weight=0.10,
                contribution=0.10,
            ),

            "arr": DimensionScore(
                score=1.0,
                weight=0.05,
                contribution=0.05,
            ),

            "customer_concentration": DimensionScore(
                score=1.0,
                weight=0.05,
                contribution=0.05,
            ),
        },

        meets_threshold=True,
    )


def make_ranked_match(
    *,
    buyer_id=None,
    business_id=None,
    rank: int = 1,
) -> RankedMatch:
    return RankedMatch(
        rank=rank,

        evaluation=make_evaluation(
            buyer_id=buyer_id,
            business_id=business_id,
        ),
    )


# ============================================================
# CANDIDATE INPUT BUILDING
# ============================================================


@patch(
    "app.matching.db_service."
    "build_business_match_input"
)
def test_build_candidate_inputs(
    mock_build_business,
):
    business_one = Mock()

    business_two = Mock()

    input_one = (
        make_business_input()
    )

    input_two = (
        make_business_input()
    )

    mock_build_business.side_effect = [
        input_one,
        input_two,
    ]

    result = _build_candidate_inputs(
        [
            business_one,
            business_two,
        ]
    )

    assert result == [
        input_one,
        input_two,
    ]

    assert (
        mock_build_business.call_count
        == 2
    )


@patch(
    "app.matching.db_service."
    "build_business_match_input"
)
def test_build_candidate_inputs_skips_incomplete_business(
    mock_build_business,
):
    incomplete_business = Mock()

    incomplete_business.id = (
        uuid4()
    )

    valid_business = Mock()

    valid_input = (
        make_business_input()
    )

    mock_build_business.side_effect = [
        MatchingDataIncompleteError(
            "Missing ARR"
        ),
        valid_input,
    ]

    result = _build_candidate_inputs(
        [
            incomplete_business,
            valid_business,
        ]
    )

    assert result == [
        valid_input,
    ]


# ============================================================
# DATABASE-BACKED MATCHING
# ============================================================


@patch(
    "app.matching.db_service."
    "upsert_match"
)
@patch(
    "app.matching.db_service."
    "rank_candidates"
)
@patch(
    "app.matching.db_service."
    "_build_candidate_inputs"
)
@patch(
    "app.matching.db_service."
    "get_candidate_businesses"
)
@patch(
    "app.matching.db_service."
    "build_buyer_match_input"
)
@patch(
    "app.matching.db_service."
    "get_buyer_preferences"
)
def test_recalculate_matches_for_buyer_success(
    mock_get_preferences,
    mock_build_buyer,
    mock_get_businesses,
    mock_build_candidates,
    mock_rank,
    mock_upsert,
):
    session = Mock()

    buyer_id = uuid4()

    business_id = uuid4()

    preferences = Mock()

    business = Mock()

    buyer_input = (
        make_buyer_input(
            buyer_id=buyer_id
        )
    )

    business_input = (
        make_business_input(
            business_id=business_id
        )
    )

    ranked = (
        make_ranked_match(
            buyer_id=buyer_id,
            business_id=business_id,
        )
    )

    mock_get_preferences.return_value = (
        preferences
    )

    mock_build_buyer.return_value = (
        buyer_input
    )

    mock_get_businesses.return_value = [
        business,
    ]

    mock_build_candidates.return_value = [
        business_input,
    ]

    mock_rank.return_value = [
        ranked,
    ]

    result = (
        recalculate_matches_for_buyer(
            session,
            buyer_id,
        )
    )

    assert result == [
        ranked,
    ]

    mock_get_preferences.assert_called_once_with(
        session,
        buyer_id,
    )

    mock_build_buyer.assert_called_once_with(
        preferences
    )

    mock_get_businesses.assert_called_once_with(
        session,
        preferences,
    )

    mock_build_candidates.assert_called_once_with(
        [
            business,
        ]
    )

    mock_rank.assert_called_once()

    mock_upsert.assert_called_once_with(
        session,
        ranked.evaluation,
    )

    session.commit.assert_called_once()

    session.rollback.assert_not_called()


# ============================================================
# NO CANDIDATES
# ============================================================


@patch(
    "app.matching.db_service."
    "get_candidate_businesses"
)
@patch(
    "app.matching.db_service."
    "build_buyer_match_input"
)
@patch(
    "app.matching.db_service."
    "get_buyer_preferences"
)
def test_no_candidate_businesses_returns_empty_list(
    mock_get_preferences,
    mock_build_buyer,
    mock_get_businesses,
):
    session = Mock()

    buyer_id = uuid4()

    preferences = Mock()

    mock_get_preferences.return_value = (
        preferences
    )

    mock_build_buyer.return_value = (
        make_buyer_input(
            buyer_id=buyer_id
        )
    )

    mock_get_businesses.return_value = (
        []
    )

    result = (
        recalculate_matches_for_buyer(
            session,
            buyer_id,
        )
    )

    assert result == []

    session.commit.assert_not_called()

    session.rollback.assert_not_called()


# ============================================================
# ALL CANDIDATES INCOMPLETE
# ============================================================


@patch(
    "app.matching.db_service."
    "_build_candidate_inputs"
)
@patch(
    "app.matching.db_service."
    "get_candidate_businesses"
)
@patch(
    "app.matching.db_service."
    "build_buyer_match_input"
)
@patch(
    "app.matching.db_service."
    "get_buyer_preferences"
)
def test_all_incomplete_candidates_returns_empty_list(
    mock_get_preferences,
    mock_build_buyer,
    mock_get_businesses,
    mock_build_candidates,
):
    session = Mock()

    buyer_id = uuid4()

    preferences = Mock()

    business = Mock()

    mock_get_preferences.return_value = (
        preferences
    )

    mock_build_buyer.return_value = (
        make_buyer_input(
            buyer_id=buyer_id
        )
    )

    mock_get_businesses.return_value = [
        business,
    ]

    mock_build_candidates.return_value = (
        []
    )

    result = (
        recalculate_matches_for_buyer(
            session,
            buyer_id,
        )
    )

    assert result == []

    session.commit.assert_not_called()

    session.rollback.assert_not_called()


# ============================================================
# TOP N + THRESHOLD
# ============================================================


@patch(
    "app.matching.db_service."
    "upsert_match"
)
@patch(
    "app.matching.db_service."
    "rank_candidates"
)
@patch(
    "app.matching.db_service."
    "_build_candidate_inputs"
)
@patch(
    "app.matching.db_service."
    "get_candidate_businesses"
)
@patch(
    "app.matching.db_service."
    "build_buyer_match_input"
)
@patch(
    "app.matching.db_service."
    "get_buyer_preferences"
)
def test_threshold_and_top_n_are_forwarded(
    mock_get_preferences,
    mock_build_buyer,
    mock_get_businesses,
    mock_build_candidates,
    mock_rank,
    mock_upsert,
):
    session = Mock()

    buyer_id = uuid4()

    preferences = Mock()

    business = Mock()

    buyer_input = (
        make_buyer_input(
            buyer_id=buyer_id
        )
    )

    business_input = (
        make_business_input()
    )

    mock_get_preferences.return_value = (
        preferences
    )

    mock_build_buyer.return_value = (
        buyer_input
    )

    mock_get_businesses.return_value = [
        business,
    ]

    mock_build_candidates.return_value = [
        business_input,
    ]

    mock_rank.return_value = []

    recalculate_matches_for_buyer(
        session,
        buyer_id,
        minimum_threshold=0.80,
        top_n=5,
    )

    mock_rank.assert_called_once_with(
        buyer_input,
        [
            business_input,
        ],
        minimum_threshold=0.80,
        top_n=5,
    )

    session.commit.assert_called_once()


# ============================================================
# INPUT VALIDATION
# ============================================================


def test_invalid_threshold_fails_before_database_work():
    session = Mock()

    with pytest.raises(
        ValueError
    ):
        recalculate_matches_for_buyer(
            session,
            uuid4(),
            minimum_threshold=1.5,
        )

    session.commit.assert_not_called()

    session.rollback.assert_not_called()


def test_zero_top_n_fails_before_database_work():
    session = Mock()

    with pytest.raises(
        ValueError
    ):
        recalculate_matches_for_buyer(
            session,
            uuid4(),
            top_n=0,
        )

    session.commit.assert_not_called()

    session.rollback.assert_not_called()


# ============================================================
# TRANSACTION FAILURE
# ============================================================


@patch(
    "app.matching.db_service."
    "get_buyer_preferences"
)
def test_unexpected_database_failure_rolls_back(
    mock_get_preferences,
):
    session = Mock()

    buyer_id = uuid4()

    mock_get_preferences.side_effect = (
        RuntimeError(
            "database unavailable"
        )
    )

    with pytest.raises(
        MatchingDatabaseServiceError
    ):
        recalculate_matches_for_buyer(
            session,
            buyer_id,
        )

    session.rollback.assert_called_once()

    session.commit.assert_not_called()