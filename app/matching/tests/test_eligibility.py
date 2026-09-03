from decimal import Decimal

from app.matching.eligibility import (
    calculate_absolute_price_ceiling,
    check_geography_eligibility,
    check_industry_eligibility,
    check_purchase_price_eligibility,
    check_sde_eligibility,
    evaluate_eligibility,
)


# ============================================================
# INDUSTRY ELIGIBILITY
# ============================================================


def test_industry_exact_match():
    assert check_industry_eligibility(
        ["HVAC", "Plumbing"],
        "Plumbing",
    )


def test_industry_is_case_insensitive():
    assert check_industry_eligibility(
        ["Plumbing"],
        "plumbing",
    )


def test_industry_mismatch():
    assert not check_industry_eligibility(
        ["HVAC"],
        "Plumbing",
    )


def test_no_industry_preference_is_unrestricted():
    assert check_industry_eligibility(
        None,
        "Plumbing",
    )


# ============================================================
# GEOGRAPHY ELIGIBILITY
# ============================================================


def test_state_geography_match():
    assert check_geography_eligibility(
        {"state": "Florida"},
        business_city="Boca Raton",
        business_county="Palm Beach",
        business_state="florida",
    )


def test_state_geography_mismatch():
    assert not check_geography_eligibility(
        {"state": "Florida"},
        business_city="Atlanta",
        business_county="Fulton",
        business_state="Georgia",
    )


def test_city_geography_match():
    assert check_geography_eligibility(
        {"city": "Boca Raton"},
        business_city="boca raton",
        business_county="Palm Beach",
        business_state="Florida",
    )


def test_county_geography_match():
    assert check_geography_eligibility(
        {"county": "Palm Beach"},
        business_city="Boca Raton",
        business_county="palm beach",
        business_state="Florida",
    )


def test_multiple_geography_constraints_match():
    assert check_geography_eligibility(
        {
            "state": "Florida",
            "county": "Palm Beach",
            "city": "Boca Raton",
        },
        business_city="Boca Raton",
        business_county="Palm Beach",
        business_state="Florida",
    )


def test_no_geography_preference_is_unrestricted():
    assert check_geography_eligibility(
        None,
        business_city="Atlanta",
        business_county="Fulton",
        business_state="Georgia",
    )


# ============================================================
# PURCHASE PRICE ELIGIBILITY
# ============================================================


def test_absolute_price_ceiling():
    ceiling = calculate_absolute_price_ceiling(
        Decimal("500000")
    )

    assert ceiling == Decimal("575000.00")


def test_purchase_price_below_maximum():
    assert check_purchase_price_eligibility(
        Decimal("500000"),
        Decimal("450000"),
    )


def test_purchase_price_at_maximum():
    assert check_purchase_price_eligibility(
        Decimal("500000"),
        Decimal("500000"),
    )


def test_purchase_price_inside_tolerance():
    assert check_purchase_price_eligibility(
        Decimal("500000"),
        Decimal("550000"),
    )


def test_purchase_price_at_absolute_ceiling():
    assert check_purchase_price_eligibility(
        Decimal("500000"),
        Decimal("575000"),
    )


def test_purchase_price_above_absolute_ceiling():
    assert not check_purchase_price_eligibility(
        Decimal("500000"),
        Decimal("576000"),
    )


def test_no_maximum_purchase_price_is_unrestricted():
    assert check_purchase_price_eligibility(
        None,
        Decimal("1000000"),
    )


# ============================================================
# SDE ELIGIBILITY
# ============================================================


def test_sde_at_minimum_is_eligible():
    assert check_sde_eligibility(
        Decimal("100000"),
        Decimal("100000"),
    )


def test_sde_above_minimum_is_eligible():
    assert check_sde_eligibility(
        Decimal("100000"),
        Decimal("150000"),
    )


def test_sde_below_minimum_is_rejected():
    assert not check_sde_eligibility(
        Decimal("100000"),
        Decimal("80000"),
    )


def test_no_minimum_sde_is_unrestricted():
    assert check_sde_eligibility(
        None,
        Decimal("50000"),
    )


# ============================================================
# COMPLETE ELIGIBILITY FLOW
# ============================================================


def test_complete_eligibility_success():
    result = evaluate_eligibility(
        target_industries=["Plumbing"],
        target_locations={
            "state": "Florida",
        },
        maximum_purchase_price=Decimal("500000"),
        minimum_sde=Decimal("100000"),
        business_industry="Plumbing",
        business_city="Boca Raton",
        business_county="Palm Beach",
        business_state="Florida",
        asking_price=Decimal("550000"),
        seller_sde=Decimal("150000"),
    )

    assert result.eligible is True
    assert result.failed_constraints == []


def test_complete_eligibility_reports_all_failures():
    result = evaluate_eligibility(
        target_industries=["HVAC"],
        target_locations={
            "state": "Florida",
        },
        maximum_purchase_price=Decimal("500000"),
        minimum_sde=Decimal("100000"),
        business_industry="Plumbing",
        business_city="Atlanta",
        business_county="Fulton",
        business_state="Georgia",
        asking_price=Decimal("900000"),
        seller_sde=Decimal("80000"),
    )

    assert result.eligible is False

    assert set(result.failed_constraints) == {
        "industry",
        "geography",
        "purchase_price",
        "sde",
    }


def test_candidate_at_price_and_sde_boundaries_passes():
    result = evaluate_eligibility(
        target_industries=["HVAC"],
        target_locations={
            "state": "Texas",
        },
        maximum_purchase_price=Decimal("500000"),
        minimum_sde=Decimal("100000"),
        business_industry="HVAC",
        business_city="Dallas",
        business_county="Dallas",
        business_state="Texas",
        asking_price=Decimal("575000"),
        seller_sde=Decimal("100000"),
    )

    assert result.eligible is True
    assert result.failed_constraints == []


def test_candidate_one_dollar_above_price_ceiling_fails():
    result = evaluate_eligibility(
        target_industries=["HVAC"],
        target_locations={
            "state": "Texas",
        },
        maximum_purchase_price=Decimal("500000"),
        minimum_sde=Decimal("100000"),
        business_industry="HVAC",
        business_city="Dallas",
        business_county="Dallas",
        business_state="Texas",
        asking_price=Decimal("575001"),
        seller_sde=Decimal("150000"),
    )

    assert result.eligible is False
    assert result.failed_constraints == [
        "purchase_price"
    ]


def test_candidate_one_dollar_below_minimum_sde_fails():
    result = evaluate_eligibility(
        target_industries=["HVAC"],
        target_locations={
            "state": "Texas",
        },
        maximum_purchase_price=Decimal("500000"),
        minimum_sde=Decimal("100000"),
        business_industry="HVAC",
        business_city="Dallas",
        business_county="Dallas",
        business_state="Texas",
        asking_price=Decimal("500000"),
        seller_sde=Decimal("99999"),
    )

    assert result.eligible is False
    assert result.failed_constraints == [
        "sde"
    ]