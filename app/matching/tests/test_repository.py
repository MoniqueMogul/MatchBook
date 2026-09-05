from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.db.db_enum import (
    BusinessStatus,
    DealPreference,
)

from app.db.db_model import (
    Business,
    BuyerPreferences,
    Match,
)

from app.matching.repository import (
    MatchingDataIncompleteError,
    MatchingRepositoryError,
    build_business_match_input,
    build_buyer_match_input,
    build_score_breakdown,
    get_existing_match,
    upsert_match,
)

from app.matching.schemas import (
    DimensionScore,
    MatchEvaluation,
)


def make_buyer_preferences() -> BuyerPreferences:
    return BuyerPreferences(
        id=uuid4(),

        buyer_id=uuid4(),

        target_industries=[
            "HVAC",
        ],

        target_locations={
            "state": "Florida",
        },

        maximum_purchase_price=Decimal(
            "500000"
        ),

        minimum_required_sde=Decimal(
            "100000"
        ),

        preferred_sde=Decimal(
            "200000"
        ),

        minimum_required_arr=Decimal(
            "200000"
        ),

        preferred_arr=Decimal(
            "500000"
        ),

        preferred_owner_hours_per_week=20,

        required_transition_training_days=30,

        deal_preference=(
            DealPreference.CASH
        ),

        minimum_years_in_operation=3,

        accepts_customer_concentration_above_25_percent=False,
    )


def make_business() -> Business:
    return Business(
        id=uuid4(),

        seller_id=uuid4(),

        business_type=(
            "Service Business"
        ),

        industry="HVAC",

        city="Orlando",

        county="Orange",

        state="Florida",

        zip_code="32801",

        years_in_operation=10,

        arr=Decimal(
            "500000"
        ),

        customer_concentration=Decimal(
            "20"
        ),

        asking_price=Decimal(
            "500000"
        ),

        sde=Decimal(
            "200000"
        ),

        owner_involvement_hours_per_week=20,

        transition_training_days=30,

        deal_preference=(
            DealPreference.CASH
        ),

        status=(
            BusinessStatus.ACTIVE
        ),
    )


def make_evaluation(
    *,
    buyer_id=None,
    business_id=None,
    score=0.855,
) -> MatchEvaluation:

    buyer_id = (
        buyer_id
        or uuid4()
    )

    business_id = (
        business_id
        or uuid4()
    )

    dimensions = {
        "industry": (
            DimensionScore(
                score=1.0,
                weight=0.0,
                contribution=0.0,
            )
        ),

        "geography": (
            DimensionScore(
                score=1.0,
                weight=0.0,
                contribution=0.0,
            )
        ),

        "purchase_price": (
            DimensionScore(
                score=0.8,
                weight=0.30,
                contribution=0.24,
            )
        ),

        "sde": (
            DimensionScore(
                score=1.0,
                weight=0.30,
                contribution=0.30,
            )
        ),

        "owner_involvement": (
            DimensionScore(
                score=0.75,
                weight=0.10,
                contribution=0.075,
            )
        ),

        "transition_training": (
            DimensionScore(
                score=0.75,
                weight=0.10,
                contribution=0.075,
            )
        ),

        "deal_preference": (
            DimensionScore(
                score=1.0,
                weight=0.10,
                contribution=0.10,
            )
        ),

        "arr": (
            DimensionScore(
                score=0.8,
                weight=0.05,
                contribution=0.04,
            )
        ),

        "customer_concentration": (
            DimensionScore(
                score=0.5,
                weight=0.05,
                contribution=0.025,
            )
        ),
    }

    return MatchEvaluation(
        buyer_id=(
            buyer_id
        ),

        business_id=(
            business_id
        ),

        eligible=True,

        failed_constraints=[],

        score=(
            score
        ),

        percentage=(
            score
            * 100
        ),

        dimensions=(
            dimensions
        ),

        meets_threshold=True,
    )


# ============================================================
# BUYER INPUT MAPPING
# ============================================================


def test_build_buyer_match_input():
    preferences = (
        make_buyer_preferences()
    )

    result = (
        build_buyer_match_input(
            preferences
        )
    )

    assert (
        result.buyer_id
        == preferences.buyer_id
    )

    assert (
        result.target_industries
        == [
            "HVAC",
        ]
    )

    assert (
        result.maximum_purchase_price
        == Decimal(
            "500000"
        )
    )

    assert (
        result.minimum_sde
        == Decimal(
            "100000"
        )
    )

    assert (
        result.preferred_sde
        == Decimal(
            "200000"
        )
    )

    assert (
        result.minimum_arr
        == Decimal(
            "200000"
        )
    )

    assert (
        result.preferred_arr
        == Decimal(
            "500000"
        )
    )

    assert (
        result.preferred_owner_hours
        == 20.0
    )

    assert (
        result.required_training_days
        == 30.0
    )

    assert (
        result.deal_preference
        == "cash"
    )

    assert (
        result.accepts_customer_concentration_above_25_percent
        is False
    )

    assert (
        result.minimum_years_in_operation
        == 3
    )


def test_buyer_missing_required_scoring_field_fails():
    preferences = (
        make_buyer_preferences()
    )

    preferences.preferred_sde = (
        None
    )

    with pytest.raises(
        MatchingDataIncompleteError
    ):
        build_buyer_match_input(
            preferences
        )


def test_missing_minimum_arr_defaults_to_zero():
    preferences = (
        make_buyer_preferences()
    )

    preferences.minimum_required_arr = (
        None
    )

    result = (
        build_buyer_match_input(
            preferences
        )
    )

    assert (
        result.minimum_arr
        == Decimal(
            "0"
        )
    )


# ============================================================
# BUSINESS INPUT MAPPING
# ============================================================


def test_build_business_match_input():
    business = (
        make_business()
    )

    result = (
        build_business_match_input(
            business
        )
    )

    assert (
        result.business_id
        == business.id
    )

    assert (
        result.industry
        == "HVAC"
    )

    assert (
        result.state
        == "Florida"
    )

    assert (
        result.asking_price
        == Decimal(
            "500000"
        )
    )

    assert (
        result.sde
        == Decimal(
            "200000"
        )
    )

    assert (
        result.arr
        == Decimal(
            "500000"
        )
    )

    assert (
        result.owner_hours
        == 20.0
    )

    assert (
        result.transition_training_days
        == 30.0
    )

    assert (
        result.deal_preference
        == "cash"
    )

    assert (
        result.largest_customer_percent
        == 20.0
    )

    assert (
        result.years_in_operation
        == 10
    )


def test_business_missing_arr_fails():
    business = (
        make_business()
    )

    business.arr = None

    with pytest.raises(
        MatchingDataIncompleteError
    ):
        build_business_match_input(
            business
        )


def test_business_missing_customer_concentration_fails():
    business = (
        make_business()
    )

    business.customer_concentration = (
        None
    )

    with pytest.raises(
        MatchingDataIncompleteError
    ):
        build_business_match_input(
            business
        )


# ============================================================
# SCORE BREAKDOWN
# ============================================================


def test_score_breakdown_contains_explainability_data():
    evaluation = (
        make_evaluation()
    )

    breakdown = (
        build_score_breakdown(
            evaluation
        )
    )

    assert (
        breakdown[
            "matching_version"
        ]
        == "v1"
    )

    assert (
        breakdown[
            "eligible"
        ]
        is True
    )

    assert (
        breakdown[
            "score"
        ]
        == pytest.approx(
            0.855
        )
    )

    assert (
        "purchase_price"
        in breakdown[
            "dimensions"
        ]
    )

    assert (
        breakdown[
            "dimensions"
        ][
            "purchase_price"
        ][
            "contribution"
        ]
        == pytest.approx(
            0.24
        )
    )


# ============================================================
# EXISTING MATCH
# ============================================================


def test_get_existing_match_returns_session_result():
    session = Mock()

    existing = Mock(
        spec=Match
    )

    session.scalar.return_value = (
        existing
    )

    result = get_existing_match(
        session,
        uuid4(),
        uuid4(),
    )

    assert (
        result
        is existing
    )

    session.scalar.assert_called_once()


# ============================================================
# UPSERT
# ============================================================


def test_upsert_creates_new_match():
    session = Mock()

    session.scalar.return_value = (
        None
    )

    evaluation = (
        make_evaluation()
    )

    result = (
        upsert_match(
            session,
            evaluation,
        )
    )

    assert isinstance(
        result,
        Match,
    )

    assert (
        result.buyer_id
        == evaluation.buyer_id
    )

    assert (
        result.business_id
        == evaluation.business_id
    )

    assert (
        result.score
        == Decimal(
            "0.855"
        )
    )

    assert (
        result.matching_version
        == "v1"
    )

    assert (
        result.price_score
        == Decimal(
            "0.8"
        )
    )

    assert (
        result.arr_score
        == Decimal(
            "0.8"
        )
    )

    assert (
        result.customer_concentration_score
        == Decimal(
            "0.5"
        )
    )

    assert (
        result.price_contribution
        == Decimal(
            "0.24"
        )
    )

    assert (
        result.arr_contribution
        == Decimal(
            "0.04"
        )
    )

    assert (
        result.customer_concentration_contribution
        == Decimal(
            "0.025"
        )
    )

    session.add.assert_called_once_with(
        result
    )

    session.flush.assert_called_once()


def test_upsert_updates_existing_match_without_duplicate():
    session = Mock()

    buyer_id = uuid4()

    business_id = uuid4()

    existing = Match(
        id=uuid4(),

        buyer_id=(
            buyer_id
        ),

        business_id=(
            business_id
        ),

        score=Decimal(
            "0.50"
        ),

        matching_version="v1",
    )

    session.scalar.return_value = (
        existing
    )

    evaluation = (
        make_evaluation(
            buyer_id=(
                buyer_id
            ),
            business_id=(
                business_id
            ),
            score=0.855,
        )
    )

    result = (
        upsert_match(
            session,
            evaluation,
        )
    )

    assert (
        result
        is existing
    )

    assert (
        result.score
        == Decimal(
            "0.855"
        )
    )

    assert (
        result.price_score
        == Decimal(
            "0.8"
        )
    )

    assert (
        result.matching_version
        == "v1"
    )

    session.add.assert_not_called()

    session.flush.assert_called_once()


def test_ineligible_evaluation_is_not_persisted():
    session = Mock()

    evaluation = MatchEvaluation(
        buyer_id=uuid4(),

        business_id=uuid4(),

        eligible=False,

        failed_constraints=[
            "industry",
        ],

        score=None,

        percentage=None,

        dimensions={},

        meets_threshold=False,
    )

    with pytest.raises(
        MatchingRepositoryError
    ):
        upsert_match(
            session,
            evaluation,
        )

    session.add.assert_not_called()


def test_match_score_breakdown_is_persisted():
    session = Mock()

    session.scalar.return_value = (
        None
    )

    evaluation = (
        make_evaluation()
    )

    result = (
        upsert_match(
            session,
            evaluation,
        )
    )

    assert (
        result.score_breakdown[
            "matching_version"
        ]
        == "v1"
    )

    assert (
        "arr"
        in result.score_breakdown[
            "dimensions"
        ]
    )

    assert (
        "customer_concentration"
        in result.score_breakdown[
            "dimensions"
        ]
    )


def test_upsert_does_not_commit_transaction():
    session = Mock()

    session.scalar.return_value = (
        None
    )

    evaluation = (
        make_evaluation()
    )

    upsert_match(
        session,
        evaluation,
    )

    session.commit.assert_not_called()

    session.flush.assert_called_once()