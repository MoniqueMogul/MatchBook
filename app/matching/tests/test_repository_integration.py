import os
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

load_dotenv()

from app.db.db_enum import (
    BusinessStatus,
    BusinessType,
    BuyerType,
    DealPreference,
    MatchStatus,
)
from app.db.db_model import (
    Business,
    BuyerPreferences,
    BuyerProfile,
    Match,
    SellerProfile,
    User,
)
from app.matching.repository import MatchingRepository


# ============================================================
# DATABASE
# ============================================================


DATABASE_URL = os.getenv("DATABASE_URL")


@pytest.fixture(scope="session")
def engine():
    """
    Connect to a REAL PostgreSQL/Supabase test database.

    We deliberately do not create or drop tables here.

    The test database must already contain the Matchbook schema.
    """

    if not DATABASE_URL:
        pytest.skip(
            "MATCHBOOK_TEST_DATABASE_URL is not configured."
        )

    test_engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    yield test_engine

    test_engine.dispose()


@pytest.fixture
def session(engine):
    """
    Each test runs inside a real PostgreSQL transaction.

    Everything inserted during the test is rolled back afterward,
    so test data should not remain in the database.
    """

    connection = engine.connect()
    transaction = connection.begin()

    test_session = Session(bind=connection)

    try:
        yield test_session
    finally:
        test_session.close()
        transaction.rollback()
        connection.close()


# ============================================================
# TEST DATA FACTORIES
# ============================================================


def create_user(
    session: Session,
    *,
    first_name: str = "Test",
    last_name: str = "User",
) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@matchbook-test.com",
        first_name=first_name,
        last_name=last_name,
    )

    session.add(user)
    session.flush()

    return user


def create_buyer(
    session: Session,
    *,
    target_industries=None,
    target_locations=None,
    maximum_purchase_price=Decimal("1000000"),
) -> BuyerPreferences:
    user = create_user(
        session,
        first_name="Buyer",
    )

    buyer = BuyerProfile(
        user_id=user.id,
        buyer_type=BuyerType.FIRST_TIME_OWNER,
    )

    session.add(buyer)
    session.flush()

    preferences = BuyerPreferences(
        buyer_id=buyer.id,

        target_industries=(
            target_industries
            if target_industries is not None
            else ["Manufacturing"]
        ),

        target_locations=(
            target_locations
            if target_locations is not None
            else [
                {
                    "state": "Texas",
                    "city": "Austin",
                    "county": "Travis",
                }
            ]
        ),

        maximum_purchase_price=maximum_purchase_price,

        minimum_required_sde=Decimal("100000"),
        preferred_sde=Decimal("200000"),

        minimum_required_arr=Decimal("500000"),
        preferred_arr=Decimal("1000000"),

        preferred_owner_hours_per_week=20,
        required_transition_training_days=30,

        deal_preference=DealPreference.EITHER,

        accepts_customer_concentration_above_25_percent=False,

        preferred_acquisition_timeline="6 months",
    )

    session.add(preferences)
    session.flush()

    return preferences


def create_business(
    session: Session,
    *,
    industry: str = "Manufacturing",
    state: str = "Texas",
    city: str = "Austin",
    county: str | None = "Travis",
    asking_price: Decimal | None = Decimal("1000000"),
    status: BusinessStatus = BusinessStatus.ACTIVE,
) -> Business:
    user = create_user(
        session,
        first_name="Seller",
    )

    seller = SellerProfile(
        user_id=user.id,
    )

    session.add(seller)
    session.flush()

    business = Business(
        seller_id=seller.id,

        idempotency_key=str(uuid4()),

        business_type=BusinessType.MANUFACTURING,

        industry=industry,

        state=state,
        city=city,
        county=county,

        asking_price=asking_price,

        sde=Decimal("200000"),
        arr=Decimal("1000000"),

        customer_concentration=Decimal("20"),

        owner_involvement_hours_per_week=20,
        transition_training_days=30,

        deal_preference=DealPreference.EITHER,

        preferred_sale_timeline="6 months",

        status=status,
    )

    session.add(business)
    session.flush()

    return business


def create_match(
    session: Session,
    *,
    buyer_id,
    business_id,
    status: MatchStatus,
) -> Match:
    match = Match(
        buyer_id=buyer_id,
        business_id=business_id,

        score=Decimal("0.8500"),

        status=status,

        matching_version="v1",
    )

    session.add(match)
    session.flush()

    return match


def business_ids(rows):
    return {
        row.id
        for row in rows
    }


def buyer_ids(rows):
    return {
        row.buyer_id
        for row in rows
    }


# ============================================================
# BUYER -> BUSINESS
# ============================================================


def test_real_db_candidate_business_requires_active_status(
    session,
):
    preferences = create_buyer(session)

    active = create_business(
        session,
        status=BusinessStatus.ACTIVE,
    )

    inactive = create_business(
        session,
        status=BusinessStatus.DRAFT,
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    result = business_ids(candidates)

    assert active.id in result
    assert inactive.id not in result


def test_real_db_candidate_business_filters_industry(
    session,
):
    preferences = create_buyer(
        session,
        target_industries=["Manufacturing"],
    )

    matching = create_business(
        session,
        industry="Manufacturing",
    )

    wrong_industry = create_business(
        session,
        industry="Healthcare",
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    result = business_ids(candidates)

    assert matching.id in result
    assert wrong_industry.id not in result


def test_real_db_candidate_business_filters_state(
    session,
):
    preferences = create_buyer(
        session,
        target_locations=[
            {
                "state": "Texas",
            }
        ],
    )

    texas = create_business(
        session,
        state="Texas",
        city="Austin",
    )

    florida = create_business(
        session,
        state="Florida",
        city="Miami",
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    result = business_ids(candidates)

    assert texas.id in result
    assert florida.id not in result


def test_real_db_candidate_business_filters_city(
    session,
):
    preferences = create_buyer(
        session,
        target_locations=[
            {
                "state": "Texas",
                "city": "Austin",
            }
        ],
    )

    austin = create_business(
        session,
        state="Texas",
        city="Austin",
    )

    dallas = create_business(
        session,
        state="Texas",
        city="Dallas",
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    result = business_ids(candidates)

    assert austin.id in result
    assert dallas.id not in result


def test_real_db_candidate_business_ignores_county(
    session,
):
    preferences = create_buyer(
        session,
        target_locations=[
            {
                "state": "Texas",
                "city": "Austin",
                "county": "Wrong County",
            }
        ],
    )

    business = create_business(
        session,
        state="Texas",
        city="Austin",
        county="Travis",
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    assert business.id in business_ids(candidates)


def test_real_db_candidate_business_supports_multiple_locations(
    session,
):
    preferences = create_buyer(
        session,
        target_locations=[
            {
                "state": "Texas",
                "city": "Austin",
            },
            {
                "state": "Florida",
                "city": "Miami",
            },
        ],
    )

    austin = create_business(
        session,
        state="Texas",
        city="Austin",
    )

    miami = create_business(
        session,
        state="Florida",
        city="Miami",
    )

    seattle = create_business(
        session,
        state="Washington",
        city="Seattle",
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    result = business_ids(candidates)

    assert austin.id in result
    assert miami.id in result
    assert seattle.id not in result


def test_real_db_candidate_business_price_tolerance_boundary(
    session,
):
    preferences = create_buyer(
        session,
        maximum_purchase_price=Decimal("1000000"),
    )

    exact_limit = create_business(
        session,
        asking_price=Decimal("1000000"),
    )

    tolerance_boundary = create_business(
        session,
        asking_price=Decimal("1150000"),
    )

    too_expensive = create_business(
        session,
        asking_price=Decimal("1150000.01"),
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    result = business_ids(candidates)

    assert exact_limit.id in result
    assert tolerance_boundary.id in result
    assert too_expensive.id not in result


def test_real_db_candidate_business_unknown_price_is_rejected(
    session,
):
    preferences = create_buyer(
        session,
        maximum_purchase_price=Decimal("1000000"),
    )

    unknown_price = create_business(
        session,
        asking_price=None,
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    assert unknown_price.id not in business_ids(candidates)


def test_real_db_candidate_business_exclusion_ids_work(
    session,
):
    preferences = create_buyer(session)

    included = create_business(session)
    excluded = create_business(session)

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences,
        excluded_business_ids={
            excluded.id,
        },
    )

    result = business_ids(candidates)

    assert included.id in result
    assert excluded.id not in result


# ============================================================
# BUSINESS -> BUYER
# ============================================================


def test_real_db_candidate_buyers_jsonb_industry_contains(
    session,
):
    business = create_business(
        session,
        industry="Manufacturing",
    )

    matching = create_buyer(
        session,
        target_industries=[
            "Technology",
            "Manufacturing",
        ],
    )

    wrong = create_buyer(
        session,
        target_industries=[
            "Healthcare",
        ],
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    result = buyer_ids(candidates)

    assert matching.buyer_id in result
    assert wrong.buyer_id not in result


def test_real_db_candidate_buyers_state_jsonb_contains_object_with_extra_keys(
    session,
):
    """
    Important PostgreSQL JSONB test.

    Stored target:
        Texas + city + county

    Repository asks whether the JSON contains:
        {"state": "Texas"}

    This verifies PostgreSQL's real JSONB containment behavior.
    """

    business = create_business(
        session,
        state="Texas",
        city="Austin",
        county="Travis",
    )

    buyer = create_buyer(
        session,
        target_locations=[
            {
                "state": "Texas",
                "city": "Dallas",
                "county": "Dallas",
            }
        ],
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    result = buyer_ids(candidates)

    assert buyer.buyer_id in result


def test_real_db_candidate_buyers_exact_city_jsonb_match(
    session,
):
    business = create_business(
        session,
        state="Texas",
        city="Austin",
    )

    matching = create_buyer(
        session,
        target_locations=[
            {
                "state": "Texas",
                "city": "Austin",
                "county": "Travis",
            }
        ],
    )

    wrong_state = create_buyer(
        session,
        target_locations=[
            {
                "state": "Florida",
                "city": "Miami",
            }
        ],
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    result = buyer_ids(candidates)

    assert matching.buyer_id in result
    assert wrong_state.buyer_id not in result


def test_real_db_candidate_buyers_county_is_ignored(
    session,
):
    business = create_business(
        session,
        state="Texas",
        city="Austin",
        county="Travis",
    )

    buyer = create_buyer(
        session,
        target_locations=[
            {
                "state": "Texas",
                "city": "Austin",
                "county": "Completely Different County",
            }
        ],
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    assert buyer.buyer_id in buyer_ids(candidates)


def test_real_db_candidate_buyers_reverse_price_tolerance(
    session,
):
    business = create_business(
        session,
        asking_price=Decimal("1150000"),
    )

    boundary_buyer = create_buyer(
        session,
        maximum_purchase_price=Decimal("1000000"),
    )

    too_low = create_buyer(
        session,
        maximum_purchase_price=Decimal("999999"),
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    result = buyer_ids(candidates)

    assert boundary_buyer.buyer_id in result
    assert too_low.buyer_id not in result


def test_real_db_candidate_buyers_null_industry_preference_matches(
    session,
):
    business = create_business(session)

    buyer = create_buyer(session)

    buyer.target_industries = None

    session.flush()

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    assert buyer.buyer_id in buyer_ids(candidates)



# ============================================================
# RELATIONSHIP LIFECYCLE
# ============================================================


def test_real_db_matched_relationship_remains_rerankable(
    session,
):
    business = create_business(session)
    buyer = create_buyer(session)

    create_match(
        session,
        buyer_id=buyer.buyer_id,
        business_id=business.id,
        status=MatchStatus.MATCHED,
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    assert buyer.buyer_id in buyer_ids(candidates)


@pytest.mark.parametrize(
    "protected_status",
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
def test_real_db_non_rerankable_relationship_is_excluded(
    session,
    protected_status,
):
    business = create_business(session)
    buyer = create_buyer(session)

    create_match(
        session,
        buyer_id=buyer.buyer_id,
        business_id=business.id,
        status=protected_status,
    )

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    assert buyer.buyer_id not in buyer_ids(candidates)


# ============================================================
# DEFENSIVE FALLBACKS
# ============================================================


@pytest.mark.parametrize(
    "missing_field",
    [
        "target_industries",
        "target_locations",
        "maximum_purchase_price",
        "minimum_required_sde",
        "preferred_sde",
        "minimum_required_arr",
        "preferred_arr",
        "preferred_owner_hours_per_week",
        "required_transition_training_days",
        "deal_preference",
        "accepts_customer_concentration_above_25_percent",
        "preferred_acquisition_timeline",
    ],
)
def test_real_db_invalid_buyer_with_one_required_field_missing_is_not_candidate(
    session,
    missing_field,
):
    """
    Defensive fallback.

    Intake should normally prevent an incomplete buyer from ever
    reaching matching.

    If bad/stale data somehow exists anyway, matching must not return
    that buyer as a candidate.
    """

    business = create_business(session)
    buyer = create_buyer(session)

    setattr(
        buyer,
        missing_field,
        None,
    )

    session.flush()

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_buyers(
        business
    )

    assert buyer.buyer_id not in buyer_ids(candidates)


@pytest.mark.parametrize(
    "missing_field",
    [
        "asking_price",
        "sde",
        "arr",
        "customer_concentration",
        "owner_involvement_hours_per_week",
        "transition_training_days",
        "deal_preference",
        "preferred_sale_timeline",
    ],
)
def test_real_db_invalid_business_with_one_required_field_missing_is_not_candidate(
    session,
    missing_field,
):
    """
    Defensive fallback.

    Intake should normally prevent an incomplete business from ever
    reaching matching.

    If bad/stale data somehow exists anyway, matching must not return
    that business as a candidate.
    """

    preferences = create_buyer(session)
    business = create_business(session)

    setattr(
        business,
        missing_field,
        None,
    )

    session.flush()

    repository = MatchingRepository(session)

    candidates = repository.get_candidate_businesses(
        preferences
    )

    assert business.id not in business_ids(candidates)