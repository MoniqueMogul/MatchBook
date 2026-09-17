from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.db.db_enum import BusinessStatus, MatchStatus
from app.matching.repository import MatchingRepository


# ============================================================
# HELPERS
# ============================================================


def make_repository():
    session = MagicMock()
    repository = MatchingRepository(session)

    return repository, session


def compile_statement(statement):
    """
    Compile using the PostgreSQL dialect.

    We intentionally do NOT use literal_binds=True because
    PostgreSQL JSONB values such as [] cannot always be rendered
    directly as SQL literals by SQLAlchemy.
    """

    compiled = statement.compile(
        dialect=postgresql.dialect()
    )

    return str(compiled), compiled.params


def captured_statement(session):
    return session.scalars.call_args.args[0]


def where_sql(statement) -> str:
    """
    Return only the WHERE portion of the compiled SQL.

    This prevents SELECT columns such as businesses.county from
    being mistaken for hard-filter conditions.
    """

    sql, _ = compile_statement(statement)

    if "WHERE " not in sql:
        return ""

    return sql.split("WHERE ", 1)[1]


def make_preferences(**overrides):
    defaults = {
        "buyer_id": uuid4(),
        "target_industries": ["Technology"],
        "target_locations": [
            {
                "state": "Texas",
                "city": "Austin",
                "county": "Travis",
            }
        ],
        "maximum_purchase_price": Decimal("1000000"),
    }

    defaults.update(overrides)

    preferences = MagicMock()

    for name, value in defaults.items():
        setattr(preferences, name, value)

    return preferences


def make_business(**overrides):
    defaults = {
        "id": uuid4(),
        "industry": "Technology",
        "state": "Texas",
        "city": "Austin",
        "county": "Travis",
        "asking_price": Decimal("1000000"),
        "status": BusinessStatus.ACTIVE,
    }

    defaults.update(overrides)

    business = MagicMock()

    for name, value in defaults.items():
        setattr(business, name, value)

    return business


# ============================================================
# BUYER -> BUSINESS
# ============================================================


def test_candidate_businesses_filters_active_businesses():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences()
    )

    statement = captured_statement(session)
    sql, params = compile_statement(statement)

    assert "businesses.status" in where_sql(statement)
    assert BusinessStatus.ACTIVE.value in params.values()


def test_candidate_businesses_filters_target_industry():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            target_industries=[
                "Technology",
                "Manufacturing",
            ]
        )
    )

    statement = captured_statement(session)
    sql, params = compile_statement(statement)

    assert "businesses.industry IN" in where_sql(statement)

    values = list(params.values())

    assert any(
        isinstance(value, list)
        and "Technology" in value
        and "Manufacturing" in value
        for value in values
    )


def test_candidate_businesses_skips_industry_filter_when_empty():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            target_industries=[]
        )
    )

    statement = captured_statement(session)

    assert "businesses.industry IN" not in where_sql(statement)


def test_candidate_businesses_filters_state():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            target_locations=[
                {
                    "state": "Texas",
                    "city": None,
                    "county": None,
                }
            ]
        )
    )

    statement = captured_statement(session)
    sql, params = compile_statement(statement)

    assert "businesses.state" in where_sql(statement)
    assert "Texas" in params.values()


def test_candidate_businesses_filters_city_when_present():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            target_locations=[
                {
                    "state": "Texas",
                    "city": "Austin",
                    "county": None,
                }
            ]
        )
    )

    statement = captured_statement(session)
    sql, params = compile_statement(statement)

    where = where_sql(statement)

    assert "businesses.state" in where
    assert "businesses.city" in where

    assert "Texas" in params.values()
    assert "Austin" in params.values()


def test_candidate_businesses_does_not_filter_county():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            target_locations=[
                {
                    "state": "Texas",
                    "city": "Austin",
                    "county": "Travis",
                }
            ]
        )
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    where = where_sql(statement)

    assert "businesses.county" not in where
    assert "Travis" not in params.values()


def test_candidate_businesses_supports_multiple_locations():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            target_locations=[
                {
                    "state": "Texas",
                    "city": "Austin",
                },
                {
                    "state": "Florida",
                    "city": "Miami",
                },
            ]
        )
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    values = list(params.values())
    where = where_sql(statement)

    assert "Texas" in values
    assert "Austin" in values
    assert "Florida" in values
    assert "Miami" in values

    assert " OR " in where


def test_candidate_businesses_applies_15_percent_price_tolerance():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            maximum_purchase_price=Decimal("1000000")
        )
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    assert Decimal("1150000.00") in params.values()


def test_candidate_businesses_rejects_unknown_price_when_buyer_has_maximum():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            maximum_purchase_price=Decimal("1000000")
        )
    )

    statement = captured_statement(session)

    assert (
        "businesses.asking_price IS NOT NULL"
        in where_sql(statement)
    )


def test_candidate_businesses_does_not_apply_price_filter_without_maximum():
    repository, session = make_repository()

    repository.get_candidate_businesses(
        make_preferences(
            maximum_purchase_price=None
        )
    )

    statement = captured_statement(session)

    where = where_sql(statement)

    assert "asking_price IS NOT NULL" not in where
    assert "asking_price <=" not in where


def test_candidate_businesses_excludes_existing_relationship_ids():
    repository, session = make_repository()

    excluded_id_1 = uuid4()
    excluded_id_2 = uuid4()

    repository.get_candidate_businesses(
        make_preferences(),
        excluded_business_ids={
            excluded_id_1,
            excluded_id_2,
        },
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    assert "NOT IN" in where_sql(statement)

    parameter_collections = [
        value
        for value in params.values()
        if isinstance(value, (list, tuple, set))
    ]

    assert any(
        excluded_id_1 in value
        and excluded_id_2 in value
        for value in parameter_collections
    )


def test_candidate_business_exclusions_work_without_price_preference():
    repository, session = make_repository()

    excluded_id = uuid4()

    repository.get_candidate_businesses(
        make_preferences(
            maximum_purchase_price=None
        ),
        excluded_business_ids={
            excluded_id
        },
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    assert "NOT IN" in where_sql(statement)

    parameter_collections = [
        value
        for value in params.values()
        if isinstance(value, (list, tuple, set))
    ]

    assert any(
        excluded_id in value
        for value in parameter_collections
    )


# ============================================================
# BUSINESS -> BUYERS
# ============================================================


def test_candidate_buyers_filters_target_industry():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business(
            industry="Technology"
        )
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    assert "target_industries" in where_sql(statement)

    assert any(
        value == ["Technology"]
        for value in params.values()
    )


def test_candidate_buyers_allows_buyers_without_industry_preference():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business()
    )

    statement = captured_statement(session)

    assert (
        "buyer_preferences.target_industries IS NULL"
        in where_sql(statement)
    )


def test_candidate_buyers_filters_business_state():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business(
            state="Texas",
            city=None,
        )
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    assert any(
        value == [{"state": "Texas"}]
        for value in params.values()
    )


def test_candidate_buyers_filters_business_city():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business(
            state="Texas",
            city="Austin",
        )
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    assert any(
        value == [
            {
                "state": "Texas",
                "city": "Austin",
            }
        ]
        for value in params.values()
    )


def test_candidate_buyers_does_not_use_county():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business(
            county="Travis"
        )
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    where = where_sql(statement)

    assert "county" not in where

    assert not any(
        "Travis" in str(value)
        for value in params.values()
    )


def test_candidate_buyers_reverse_price_tolerance():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business(
            asking_price=Decimal("1150000")
        )
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    assert Decimal("1E+6") in params.values()


def test_candidate_buyers_allows_unlimited_budget():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business(
            asking_price=Decimal("1000000")
        )
    )

    statement = captured_statement(session)

    assert (
        "maximum_purchase_price IS NULL"
        in where_sql(statement)
    )


def test_candidate_buyers_unknown_business_price_does_not_apply_budget_filter():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business(
            asking_price=None
        )
    )

    statement = captured_statement(session)

    assert (
        "maximum_purchase_price >="
        not in where_sql(statement)
    )


# ============================================================
# RELATIONSHIP LIFECYCLE
# ============================================================


def test_candidate_buyers_excludes_non_rerankable_relationships():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business()
    )

    statement = captured_statement(session)

    where = where_sql(statement)

    assert "EXISTS" in where
    assert "matches" in where.lower()
    assert "NOT IN" in where


def test_candidate_buyers_keeps_matched_relationship_rerankable():
    repository, session = make_repository()

    repository.get_candidate_buyers(
        make_business()
    )

    statement = captured_statement(session)
    _, params = compile_statement(statement)

    parameter_collections = [
        value
        for value in params.values()
        if isinstance(value, (list, tuple, set))
    ]

    assert any(
        MatchStatus.MATCHED in value
        or MatchStatus.MATCHED.value in value
        for value in parameter_collections
    )

# ============================================================
# RETURN BEHAVIOUR
# ============================================================


def test_candidate_businesses_returns_scalars_as_list():
    repository, session = make_repository()

    business_1 = make_business()
    business_2 = make_business()

    session.scalars.return_value.all.return_value = [
        business_1,
        business_2,
    ]

    result = repository.get_candidate_businesses(
        make_preferences()
    )

    assert result == [
        business_1,
        business_2,
    ]


def test_candidate_buyers_returns_scalars_as_list():
    repository, session = make_repository()

    buyer_1 = MagicMock()
    buyer_2 = MagicMock()

    session.scalars.return_value.all.return_value = [
        buyer_1,
        buyer_2,
    ]

    result = repository.get_candidate_buyers(
        make_business()
    )

    assert result == [
        buyer_1,
        buyer_2,
    ]