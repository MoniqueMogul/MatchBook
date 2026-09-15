from decimal import Decimal

import pytest

from app.matching.scoring import (
    calculate_arr_score,
    calculate_customer_concentration_score,
    calculate_deal_score,
    calculate_geography_score,
    calculate_industry_score,
    calculate_match_score,
    calculate_owner_involvement_score,
    calculate_price_score,
    calculate_sde_score,
    calculate_training_score,
)


# ============================================================
# INDUSTRY
# ============================================================


def test_industry_match_score():
    assert calculate_industry_score(True) == 1.0


def test_industry_mismatch_score():
    assert calculate_industry_score(False) == 0.0


# ============================================================
# GEOGRAPHY
# ============================================================


def test_geography_match_score():
    assert calculate_geography_score(True) == 1.0


def test_geography_mismatch_score():
    assert calculate_geography_score(False) == 0.0


# ============================================================
# PURCHASE PRICE
# ============================================================


@pytest.mark.parametrize(
    "seller_price, expected_score",
    [
        ("450000", 1.00),
        ("500000", 1.00),
        ("515000", 0.80),
        ("530000", 0.60),
        ("545000", 0.40),
        ("560000", 0.20),
        ("575000", 0.00),
        ("576000", 0.00),
    ],
)
def test_price_formula_examples(
    seller_price,
    expected_score,
):
    score = calculate_price_score(
        maximum_purchase_price=Decimal("500000"),
        seller_price=Decimal(seller_price),
    )

    assert score == pytest.approx(
        expected_score
    )


# ============================================================
# SDE
# ============================================================


@pytest.mark.parametrize(
    "seller_sde, expected_score",
    [
        ("80000", 0.00),
        ("100000", 0.00),
        ("125000", 0.25),
        ("150000", 0.50),
        ("175000", 0.75),
        ("200000", 1.00),
        ("250000", 1.00),
    ],
)
def test_sde_formula_examples(
    seller_sde,
    expected_score,
):
    score = calculate_sde_score(
        minimum_sde=Decimal("100000"),
        preferred_sde=Decimal("200000"),
        seller_sde=Decimal(seller_sde),
    )

    assert score == pytest.approx(
        expected_score
    )


# ============================================================
# OWNER INVOLVEMENT
# ============================================================


@pytest.mark.parametrize(
    "seller_hours, expected_score",
    [
        (5, 1.00),
        (10, 1.00),
        (15, 1.00),
        (20, 1.00),
        (25, 0.75),
        (30, 0.50),
        (35, 0.25),
        (40, 0.00),
        (45, 0.00),
    ],
)
def test_owner_involvement_formula_examples(
    seller_hours,
    expected_score,
):
    score = calculate_owner_involvement_score(
        buyer_preferred_hours=20,
        seller_owner_hours=seller_hours,
    )

    assert score == pytest.approx(
        expected_score
    )


# ============================================================
# TRAINING
# ============================================================


@pytest.mark.parametrize(
    "seller_training, expected_score",
    [
        (0, 0.00),
        (7, 7 / 30),
        (15, 0.50),
        (22, 22 / 30),
        (30, 1.00),
        (45, 1.00),
    ],
)
def test_training_formula_examples(
    seller_training,
    expected_score,
):
    score = calculate_training_score(
        buyer_required_training_days=30,
        seller_offered_training_days=seller_training,
    )

    assert score == pytest.approx(
        expected_score
    )


# ============================================================
# DEAL PREFERENCE
# ============================================================


@pytest.mark.parametrize(
    (
        "buyer_preference,"
        "seller_preference,"
        "expected_score"
    ),
    [
        ("cash", "cash", 1.00),
        ("cash", "financing", 0.50),
        ("cash", "either", 1.00),
        ("financing", "cash", 0.50),
        ("financing", "financing", 1.00),
        ("financing", "either", 1.00),
        ("either", "cash", 1.00),
        ("either", "financing", 1.00),
        ("either", "either", 1.00),
    ],
)
def test_deal_compatibility_table(
    buyer_preference,
    seller_preference,
    expected_score,
):
    score = calculate_deal_score(
        buyer_preference,
        seller_preference,
    )

    assert score == pytest.approx(
        expected_score
    )


def test_deal_score_is_case_insensitive():
    assert calculate_deal_score(
        "Cash",
        "EITHER",
    ) == 1.0


def test_invalid_deal_preference_fails():
    with pytest.raises(ValueError):
        calculate_deal_score(
            "crypto",
            "cash",
        )


# ============================================================
# ARR
# ============================================================


@pytest.mark.parametrize(
    "seller_arr, expected_score",
    [
        ("100000", 0.00),
        ("200000", 0.00),
        ("275000", 0.25),
        ("350000", 0.50),
        ("425000", 0.75),
        ("500000", 1.00),
        ("650000", 1.00),
    ],
)
def test_arr_formula_examples(
    seller_arr,
    expected_score,
):
    score = calculate_arr_score(
        minimum_arr=Decimal("200000"),
        preferred_arr=Decimal("500000"),
        seller_arr=Decimal(seller_arr),
    )

    assert score == pytest.approx(
        expected_score
    )


# ============================================================
# CUSTOMER CONCENTRATION
# ============================================================


@pytest.mark.parametrize(
    (
        "buyer_accepts,"
        "seller_concentration,"
        "expected_score"
    ),
    [
        (True, 10, 1.00),
        (True, 25, 1.00),
        (True, 35, 1.00),
        (True, 50, 1.00),
        (False, 10, 1.00),
        (False, 25, 1.00),
        (False, 30, 0.50),
        (False, 50, 0.50),
    ],
)
def test_customer_concentration_examples(
    buyer_accepts,
    seller_concentration,
    expected_score,
):
    score = (
        calculate_customer_concentration_score(
            buyer_accepts,
            seller_concentration,
        )
    )

    assert score == pytest.approx(
        expected_score
    )


def test_customer_concentration_rejects_invalid_percent():
    with pytest.raises(ValueError):
        calculate_customer_concentration_score(
            False,
            125,
        )


# ============================================================
# FINAL MATCH SCORE
# ============================================================


def test_final_match_score_from_specification():
    """
    Reproduce the exact worked example from Tim's V1
    Matching Formula document.

    Expected:
        Match Score = 0.855
        Match Percentage = 85.5%
    """

    result = calculate_match_score(
        industry_score=1.00,
        geography_score=1.00,
        price_score=0.80,
        sde_score=1.00,
        owner_involvement_score=0.75,
        training_score=0.75,
        deal_score=1.00,
        arr_score=0.80,
        customer_concentration_score=0.50,
    )

    assert result.industry_contribution == pytest.approx(
        0.00
    )

    assert result.geography_contribution == pytest.approx(
        0.00
    )

    assert result.price_contribution == pytest.approx(
        0.24
    )

    assert result.sde_contribution == pytest.approx(
        0.30
    )

    assert (
        result.owner_involvement_contribution
        == pytest.approx(0.075)
    )

    assert result.training_contribution == pytest.approx(
        0.075
    )

    assert result.deal_contribution == pytest.approx(
        0.10
    )

    assert result.arr_contribution == pytest.approx(
        0.04
    )

    assert (
        result.customer_concentration_contribution
        == pytest.approx(0.025)
    )

    assert result.match_score == pytest.approx(
        0.855
    )

    assert result.match_percentage == pytest.approx(
        85.5
    )


def test_perfect_match_scores_100_percent():
    result = calculate_match_score(
        industry_score=1.0,
        geography_score=1.0,
        price_score=1.0,
        sde_score=1.0,
        owner_involvement_score=1.0,
        training_score=1.0,
        deal_score=1.0,
        arr_score=1.0,
        customer_concentration_score=1.0,
    )

    assert result.match_score == pytest.approx(
        1.0
    )

    assert result.match_percentage == pytest.approx(
        100.0
    )


def test_industry_and_geography_do_not_change_v1_ranking():
    """
    Industry and Geography exist in the scoring architecture,
    but their V1 weights are zero.
    """

    result = calculate_match_score(
        industry_score=0.0,
        geography_score=0.0,
        price_score=1.0,
        sde_score=1.0,
        owner_involvement_score=1.0,
        training_score=1.0,
        deal_score=1.0,
        arr_score=1.0,
        customer_concentration_score=1.0,
    )

    assert result.match_score == pytest.approx(
        1.0
    )


# ============================================================
# VALIDATION / EDGE CASES
# ============================================================


def test_price_rejects_zero_maximum():
    with pytest.raises(ValueError):
        calculate_price_score(
            Decimal("0"),
            Decimal("100000"),
        )


def test_owner_involvement_zero_preferred_hours():
    assert calculate_owner_involvement_score(
        buyer_preferred_hours=0,
        seller_owner_hours=10,
    ) == 0.0


def test_zero_required_training_is_fully_satisfied():
    assert calculate_training_score(
        buyer_required_training_days=0,
        seller_offered_training_days=0,
    ) == 1.0


def test_match_score_clamps_scores():
    result = calculate_match_score(
        industry_score=2.0,
        geography_score=2.0,
        price_score=2.0,
        sde_score=2.0,
        owner_involvement_score=2.0,
        training_score=2.0,
        deal_score=2.0,
        arr_score=2.0,
        customer_concentration_score=2.0,
    )

    assert result.match_score == pytest.approx(
        1.0
    )