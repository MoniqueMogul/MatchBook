from decimal import Decimal

import pytest

from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
)

from app.matching.service import (
    evaluate_candidate,
    rank_candidates,
)


def make_buyer() -> BuyerMatchInput:
    return BuyerMatchInput(
        buyer_id=1,
        target_industries=["HVAC"],
        target_locations={
            "state": "Florida",
        },
        maximum_purchase_price=Decimal("500000"),
        minimum_sde=Decimal("100000"),
        preferred_sde=Decimal("200000"),
        preferred_owner_hours=20,
        required_training_days=30,
        deal_preference="cash",
        minimum_arr=Decimal("200000"),
        preferred_arr=Decimal("500000"),
        accepts_customer_concentration_above_25_percent=False,
    )


def make_business(
    *,
    business_id: int = 100,
    industry: str = "HVAC",
    state: str = "Florida",
    asking_price: str = "500000",
    sde: str = "200000",
    owner_hours: float = 20,
    training_days: float = 30,
    deal_preference: str = "cash",
    arr: str = "500000",
    concentration: float = 20,
) -> BusinessMatchInput:
    return BusinessMatchInput(
        business_id=business_id,
        industry=industry,
        city="Orlando",
        county="Orange",
        state=state,
        asking_price=Decimal(asking_price),
        sde=Decimal(sde),
        owner_hours=owner_hours,
        transition_training_days=training_days,
        deal_preference=deal_preference,
        arr=Decimal(arr),
        largest_customer_percent=concentration,
    )


# ============================================================
# SINGLE-CANDIDATE EVALUATION
# ============================================================


def test_perfect_candidate_scores_100_percent():
    buyer = make_buyer()
    business = make_business()

    result = evaluate_candidate(
        buyer,
        business,
    )

    assert result.eligible is True
    assert result.failed_constraints == []

    assert result.score == pytest.approx(1.0)
    assert result.percentage == pytest.approx(100.0)

    assert result.meets_threshold is True


def test_industry_failure_stops_scoring():
    buyer = make_buyer()

    business = make_business(
        industry="Plumbing",
    )

    result = evaluate_candidate(
        buyer,
        business,
    )

    assert result.eligible is False

    assert "industry" in result.failed_constraints

    assert result.score is None
    assert result.percentage is None

    assert result.dimensions == {}

    assert result.meets_threshold is False


def test_geography_failure_stops_scoring():
    buyer = make_buyer()

    business = make_business(
        state="Georgia",
    )

    result = evaluate_candidate(
        buyer,
        business,
    )

    assert result.eligible is False

    assert "geography" in result.failed_constraints

    assert result.score is None


def test_price_above_hard_ceiling_rejected():
    buyer = make_buyer()

    business = make_business(
        asking_price="600000",
    )

    result = evaluate_candidate(
        buyer,
        business,
    )

    assert result.eligible is False

    assert "purchase_price" in (
        result.failed_constraints
    )


def test_sde_below_minimum_rejected():
    buyer = make_buyer()

    business = make_business(
        sde="80000",
    )

    result = evaluate_candidate(
        buyer,
        business,
    )

    assert result.eligible is False

    assert "sde" in result.failed_constraints


def test_score_breakdown_contains_all_dimensions():
    buyer = make_buyer()
    business = make_business()

    result = evaluate_candidate(
        buyer,
        business,
    )

    expected_dimensions = {
        "industry",
        "geography",
        "purchase_price",
        "sde",
        "owner_involvement",
        "transition_training",
        "deal_preference",
        "arr",
        "customer_concentration",
    }

    assert set(
        result.dimensions.keys()
    ) == expected_dimensions


def test_dimension_weights_total_one():
    buyer = make_buyer()
    business = make_business()

    result = evaluate_candidate(
        buyer,
        business,
    )

    total_weight = sum(
        dimension.weight
        for dimension in result.dimensions.values()
    )

    assert total_weight == pytest.approx(1.0)


def test_dimension_contributions_equal_final_score():
    buyer = make_buyer()

    business = make_business(
        asking_price="530000",
        sde="150000",
        owner_hours=30,
        training_days=15,
        deal_preference="financing",
        arr="350000",
        concentration=40,
    )

    result = evaluate_candidate(
        buyer,
        business,
        minimum_threshold=0.0,
    )

    contribution_total = sum(
        dimension.contribution
        for dimension in result.dimensions.values()
    )

    assert contribution_total == pytest.approx(
        result.score
    )


# ============================================================
# THRESHOLD
# ============================================================


def test_candidate_above_threshold_passes():
    buyer = make_buyer()
    business = make_business()

    result = evaluate_candidate(
        buyer,
        business,
        minimum_threshold=0.70,
    )

    assert result.meets_threshold is True


def test_candidate_below_custom_threshold_fails():
    buyer = make_buyer()

    business = make_business(
        asking_price="560000",
        sde="110000",
        owner_hours=35,
        training_days=5,
        deal_preference="financing",
        arr="210000",
        concentration=50,
    )

    result = evaluate_candidate(
        buyer,
        business,
        minimum_threshold=0.95,
    )

    assert result.eligible is True
    assert result.meets_threshold is False


# ============================================================
# RANKING
# ============================================================


def test_rank_candidates_orders_highest_score_first():
    buyer = make_buyer()

    excellent = make_business(
        business_id=1,
    )

    medium = make_business(
        business_id=2,
        asking_price="530000",
        sde="150000",
        owner_hours=25,
        training_days=20,
        arr="350000",
    )

    weaker = make_business(
        business_id=3,
        asking_price="550000",
        sde="120000",
        owner_hours=30,
        training_days=10,
        deal_preference="financing",
        arr="250000",
        concentration=40,
    )

    ranked = rank_candidates(
        buyer,
        [
            weaker,
            medium,
            excellent,
        ],
        minimum_threshold=0.0,
    )

    assert len(ranked) == 3

    assert ranked[0].rank == 1
    assert ranked[0].evaluation.business_id == 1

    assert ranked[1].rank == 2
    assert ranked[1].evaluation.business_id == 2

    assert ranked[2].rank == 3
    assert ranked[2].evaluation.business_id == 3


def test_ranking_excludes_ineligible_business():
    buyer = make_buyer()

    eligible = make_business(
        business_id=1,
    )

    ineligible = make_business(
        business_id=2,
        industry="Plumbing",
    )

    ranked = rank_candidates(
        buyer,
        [
            ineligible,
            eligible,
        ],
        minimum_threshold=0.0,
    )

    assert len(ranked) == 1

    assert (
        ranked[0].evaluation.business_id
        == 1
    )


def test_ranking_excludes_candidates_below_threshold():
    buyer = make_buyer()

    excellent = make_business(
        business_id=1,
    )

    weak = make_business(
        business_id=2,
        asking_price="560000",
        sde="110000",
        owner_hours=35,
        training_days=5,
        deal_preference="financing",
        arr="210000",
        concentration=50,
    )

    ranked = rank_candidates(
        buyer,
        [
            weak,
            excellent,
        ],
        minimum_threshold=0.90,
    )

    assert len(ranked) == 1

    assert (
        ranked[0].evaluation.business_id
        == 1
    )


def test_top_n_limits_results():
    buyer = make_buyer()

    businesses = [
        make_business(
            business_id=index,
        )
        for index in range(
            1,
            11,
        )
    ]

    ranked = rank_candidates(
        buyer,
        businesses,
        minimum_threshold=0.0,
        top_n=5,
    )

    assert len(ranked) == 5


def test_top_n_zero_returns_empty_list():
    buyer = make_buyer()

    ranked = rank_candidates(
        buyer,
        [
            make_business(
                business_id=1,
            )
        ],
        minimum_threshold=0.0,
        top_n=0,
    )

    assert ranked == []


# ============================================================
# DETERMINISM
# ============================================================


def test_same_inputs_produce_same_result():
    buyer = make_buyer()

    business = make_business(
        asking_price="530000",
        sde="150000",
        owner_hours=25,
        training_days=15,
        arr="350000",
        concentration=30,
    )

    result_one = evaluate_candidate(
        buyer,
        business,
    )

    result_two = evaluate_candidate(
        buyer,
        business,
    )

    assert result_one == result_two