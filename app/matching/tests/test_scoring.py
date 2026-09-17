from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.db_enum import DealPreference
from app.matching.scoring import (
    score_arr,
    score_candidate,
    score_customer_concentration,
    score_deal_preference,
    score_owner_involvement,
    score_price,
    score_sde,
    score_transition_training,
)
from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
)


# ============================================================
# TEST DATA
# ============================================================


def make_buyer(**overrides) -> BuyerMatchInput:
    data = {
        "buyer_id": uuid4(),
        "target_industries": ["HVAC"],
        "target_locations": [
            {
                "state": "Florida",
                "city": "Orlando",
                "county": "Orange",
            }
        ],
        "maximum_purchase_price": Decimal("500000"),
        "minimum_sde": Decimal("100000"),
        "preferred_sde": Decimal("200000"),
        "minimum_arr": Decimal("200000"),
        "preferred_arr": Decimal("500000"),
        "preferred_owner_hours": 20,
        "required_training_days": 30,
        "deal_preference": DealPreference.CASH,
        "accepts_customer_concentration_above_25_percent": False,
    }

    data.update(overrides)

    return BuyerMatchInput(**data)


def make_business(**overrides) -> BusinessMatchInput:
    data = {
        "business_id": uuid4(),
        "industry": "HVAC",
        "city": "Orlando",
        "county": "Orange",
        "state": "Florida",
        "asking_price": Decimal("500000"),
        "sde": Decimal("200000"),
        "arr": Decimal("500000"),
        "owner_hours": 20,
        "transition_training_days": 30,
        "deal_preference": DealPreference.CASH,
        "customer_concentration": Decimal("20"),
    }

    data.update(overrides)

    return BusinessMatchInput(**data)


# ============================================================
# PRICE
# ============================================================


def test_price_at_maximum_scores_one():
    score = score_price(
        maximum_price=Decimal("500000"),
        asking_price=Decimal("500000"),
    )

    assert score == pytest.approx(1.0)


def test_price_below_maximum_does_not_score_above_one():
    score = score_price(
        maximum_price=Decimal("500000"),
        asking_price=Decimal("1"),
    )

    assert score == pytest.approx(1.0)


def test_price_halfway_through_tolerance_scores_half():
    # 15% tolerance on $500,000 = $75,000.
    # Halfway through that range = $537,500.
    score = score_price(
        maximum_price=Decimal("500000"),
        asking_price=Decimal("537500"),
    )

    assert score == pytest.approx(0.5)


def test_price_exactly_at_tolerance_ceiling_scores_zero():
    score = score_price(
        maximum_price=Decimal("500000"),
        asking_price=Decimal("575000"),
    )

    assert score == pytest.approx(0.0)


def test_price_above_tolerance_ceiling_still_scores_zero():
    """
    Repository should normally remove this candidate.

    Scoring must still fail closed if one slips through.
    """

    score = score_price(
        maximum_price=Decimal("500000"),
        asking_price=Decimal("900000"),
    )

    assert score == pytest.approx(0.0)


# ============================================================
# SDE
# ============================================================


def test_sde_below_minimum_scores_zero():
    score = score_sde(
        minimum_sde=Decimal("100000"),
        preferred_sde=Decimal("200000"),
        business_sde=Decimal("99999"),
    )

    assert score == pytest.approx(0.0)


def test_sde_exactly_at_minimum_scores_zero():
    score = score_sde(
        minimum_sde=Decimal("100000"),
        preferred_sde=Decimal("200000"),
        business_sde=Decimal("100000"),
    )

    assert score == pytest.approx(0.0)


def test_sde_halfway_between_minimum_and_preferred_scores_half():
    score = score_sde(
        minimum_sde=Decimal("100000"),
        preferred_sde=Decimal("200000"),
        business_sde=Decimal("150000"),
    )

    assert score == pytest.approx(0.5)


def test_sde_at_preferred_scores_one():
    score = score_sde(
        minimum_sde=Decimal("100000"),
        preferred_sde=Decimal("200000"),
        business_sde=Decimal("200000"),
    )

    assert score == pytest.approx(1.0)


def test_sde_above_preferred_cannot_exceed_one():
    score = score_sde(
        minimum_sde=Decimal("100000"),
        preferred_sde=Decimal("200000"),
        business_sde=Decimal("999999999"),
    )

    assert score == pytest.approx(1.0)


# ============================================================
# ARR
# ============================================================


def test_arr_below_minimum_scores_zero():
    score = score_arr(
        minimum_arr=Decimal("200000"),
        preferred_arr=Decimal("500000"),
        business_arr=Decimal("100000"),
    )

    assert score == pytest.approx(0.0)


def test_arr_between_minimum_and_preferred_is_proportional():
    score = score_arr(
        minimum_arr=Decimal("200000"),
        preferred_arr=Decimal("500000"),
        business_arr=Decimal("350000"),
    )

    assert score == pytest.approx(0.5)


def test_arr_at_preferred_scores_one():
    score = score_arr(
        minimum_arr=Decimal("200000"),
        preferred_arr=Decimal("500000"),
        business_arr=Decimal("500000"),
    )

    assert score == pytest.approx(1.0)


# ============================================================
# OWNER INVOLVEMENT
# ============================================================


def test_owner_hours_at_preference_scores_one():
    score = score_owner_involvement(
        preferred_hours=20,
        actual_hours=20,
    )

    assert score == pytest.approx(1.0)


def test_fewer_owner_hours_scores_one():
    score = score_owner_involvement(
        preferred_hours=20,
        actual_hours=5,
    )

    assert score == pytest.approx(1.0)


def test_double_preferred_owner_hours_scores_half():
    score = score_owner_involvement(
        preferred_hours=20,
        actual_hours=40,
    )

    assert score == pytest.approx(0.5)


def test_zero_owner_hours_scores_one():
    score = score_owner_involvement(
        preferred_hours=20,
        actual_hours=0,
    )

    assert score == pytest.approx(1.0)


# ============================================================
# TRANSITION TRAINING
# ============================================================


def test_exact_required_training_scores_one():
    score = score_transition_training(
        required_days=30,
        available_days=30,
    )

    assert score == pytest.approx(1.0)


def test_more_training_does_not_score_above_one():
    score = score_transition_training(
        required_days=30,
        available_days=365,
    )

    assert score == pytest.approx(1.0)


def test_half_required_training_scores_half():
    score = score_transition_training(
        required_days=30,
        available_days=15,
    )

    assert score == pytest.approx(0.5)


def test_zero_required_training_scores_one():
    score = score_transition_training(
        required_days=0,
        available_days=0,
    )

    assert score == pytest.approx(1.0)


# ============================================================
# DEAL PREFERENCE
# ============================================================


@pytest.mark.parametrize(
    (
        "buyer_preference",
        "business_preference",
        "expected",
    ),
    [
        (DealPreference.CASH, DealPreference.CASH, 1.0),
        (DealPreference.CASH, DealPreference.FINANCING, 0.5),
        (DealPreference.CASH, DealPreference.EITHER, 1.0),

        (DealPreference.FINANCING, DealPreference.CASH, 0.5),
        (DealPreference.FINANCING, DealPreference.FINANCING, 1.0),
        (DealPreference.FINANCING, DealPreference.EITHER, 1.0),

        (DealPreference.EITHER, DealPreference.CASH, 1.0),
        (DealPreference.EITHER, DealPreference.FINANCING, 1.0),
        (DealPreference.EITHER, DealPreference.EITHER, 1.0),
    ],
)
def test_every_deal_compatibility_combination(
    buyer_preference,
    business_preference,
    expected,
):
    score = score_deal_preference(
        buyer_preference=buyer_preference,
        business_preference=business_preference,
    )

    assert score == pytest.approx(expected)


# ============================================================
# CUSTOMER CONCENTRATION
# ============================================================


def test_buyer_accepting_high_concentration_scores_one():
    score = score_customer_concentration(
        accepts_above_25_percent=True,
        concentration=Decimal("99"),
    )

    assert score == pytest.approx(1.0)


def test_exactly_25_percent_scores_one():
    score = score_customer_concentration(
        accepts_above_25_percent=False,
        concentration=Decimal("25"),
    )

    assert score == pytest.approx(1.0)


def test_above_25_percent_scores_zero_when_not_accepted():
    score = score_customer_concentration(
        accepts_above_25_percent=False,
        concentration=Decimal("25.0001"),
    )

    assert score == pytest.approx(0.0)


# ============================================================
# COMPLETE CANDIDATE
# ============================================================


def test_perfect_candidate_scores_one():
    result = score_candidate(
        buyer=make_buyer(),
        business=make_business(),
    )

    assert result.score == pytest.approx(1.0)


def test_every_dimension_is_present_for_complete_candidate():
    result = score_candidate(
        buyer=make_buyer(),
        business=make_business(),
    )

    assert set(result.dimensions) == {
        "purchase_price",
        "sde",
        "arr",
        "owner_involvement",
        "transition_training",
        "deal_preference",
        "customer_concentration",
    }


def test_dimension_weights_total_one():
    result = score_candidate(
        buyer=make_buyer(),
        business=make_business(),
    )

    total_weight = sum(
        dimension.weight
        for dimension in result.dimensions.values()
    )

    assert total_weight == pytest.approx(1.0)


def test_dimension_contributions_equal_final_score():
    result = score_candidate(
        buyer=make_buyer(),
        business=make_business(),
    )

    total_contribution = sum(
        dimension.contribution
        for dimension in result.dimensions.values()
    )

    assert result.score == pytest.approx(
        total_contribution
    )


# ============================================================
# FAIL-CLOSED MISSING DATA
# ============================================================


@pytest.mark.parametrize(
    ("side", "field"),
    [
        ("buyer", "maximum_purchase_price"),
        ("buyer", "minimum_sde"),
        ("buyer", "preferred_sde"),
        ("buyer", "minimum_arr"),
        ("buyer", "preferred_arr"),
        ("buyer", "preferred_owner_hours"),
        ("buyer", "required_training_days"),
        ("buyer", "deal_preference"),
        (
            "buyer",
            "accepts_customer_concentration_above_25_percent",
        ),

        ("business", "asking_price"),
        ("business", "sde"),
        ("business", "arr"),
        ("business", "owner_hours"),
        ("business", "transition_training_days"),
        ("business", "deal_preference"),
        ("business", "customer_concentration"),
    ],
)
def test_any_missing_required_scoring_field_forces_candidate_to_zero(
    side,
    field,
):
    buyer_overrides = {}
    business_overrides = {}

    if side == "buyer":
        buyer_overrides[field] = None
    else:
        business_overrides[field] = None

    result = score_candidate(
        buyer=make_buyer(**buyer_overrides),
        business=make_business(**business_overrides),
    )

    assert result.score == pytest.approx(0.0)
    assert result.dimensions == {}


# ============================================================
# SCORE SAFETY INVARIANTS
# ============================================================


@pytest.mark.parametrize(
    "business",
    [
        make_business(),
        make_business(
            asking_price=Decimal("575000"),
        ),
        make_business(
            sde=Decimal("100000"),
        ),
        make_business(
            arr=Decimal("200000"),
        ),
        make_business(
            owner_hours=1000,
        ),
        make_business(
            transition_training_days=0,
        ),
        make_business(
            customer_concentration=Decimal("100"),
        ),
    ],
)
def test_final_score_can_never_leave_zero_to_one_range(
    business,
):
    result = score_candidate(
        buyer=make_buyer(),
        business=business,
    )

    assert 0.0 <= result.score <= 1.0