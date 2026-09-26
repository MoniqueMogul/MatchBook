"""
Integration tests for IntakeService + IntakeRepository.

Scope
-----
These tests intentionally DO NOT test:

- FastAPI routes
- authentication
- HTTP status codes
- response schemas
- LocationIQ
- frontend behavior
- outbox publishing
- Celery / RabbitMQ

They test only:

    IntakeService
        ↓
    IntakeRepository
        ↓
    PostgreSQL

Operations under test:

1. Buyer profile upsert
2. Buyer preferences upsert
3. Business create
4. Business update

The tests verify:

- records are actually persisted
- returned ORM objects contain the expected state
- upserts do not create duplicate rows
- partial updates preserve untouched fields
- foreign ownership is rejected
- missing prerequisite records are rejected
- business creation is idempotent
- service commits successful operations
- service rolls back failed operations

IMPORTANT:
These tests require PostgreSQL.

Do NOT use SQLite because the Intake repository uses:

- PostgreSQL INSERT ... ON CONFLICT
- JSONB
- PostgreSQL UUID behavior

These tests use DATABASE_URL and therefore may run against a
real development PostgreSQL database.

Every test-created user uses an email beginning with "pytest-".
Every test-created business uses an idempotency key beginning
with "pytest-".

The cleanup fixture deletes only records belonging to those
test users/businesses.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select, delete
from sqlalchemy.orm import Session, sessionmaker

from app.db.db_model import (
    Business,
    BuyerPreferences,
    BuyerProfile,
    SellerProfile,
    User,
)

from app.intake.repository import (
    IntakeNotFoundError,
    IntakeRepository,
)

from app.intake.schemas.business import (
    BusinessCreate,
    BusinessUpdate,
)

from app.intake.schemas.buyer import (
    BuyerProfileCreate,
    BuyerProfileUpdate,
)

from app.intake.schemas.buyer_preferences import (
    BuyerPreferencesUpsert,
)

from app.intake.service import IntakeService


# ============================================================
# DATABASE
# ============================================================
load_dotenv()

TEST_DATABASE_URL = os.getenv("DATABASE_URL")

if TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgresql://"):
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


@pytest.fixture(scope="session")
def test_engine():
    """
    Connect to the configured PostgreSQL database.

    IMPORTANT:
    This fixture does NOT create or drop tables.

    The database schema is expected to already exist.
    """

    if not TEST_DATABASE_URL:
        pytest.fail("DATABASE_URL is not configured.")

    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )

    # Fail immediately if the configured database cannot be reached.
    with engine.connect():
        pass

    yield engine

    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """
    Give each test a real SQLAlchemy Session.

    IntakeService is allowed to call commit() normally so that these
    tests exercise the real service transaction behavior.

    After each test, only pytest-owned rows are removed.
    """

    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    session = TestingSessionLocal()

    try:
        yield session

    finally:
        # End a failed/incomplete transaction before cleanup.
        session.rollback()

        # --------------------------------------------------------
        # BUSINESS
        # --------------------------------------------------------
        #
        # Business must be deleted before SellerProfile because of
        # the foreign key from Business.seller_id.
        #

        session.execute(
            delete(Business).where(
                Business.idempotency_key.like("pytest-%")
            )
        )

        # --------------------------------------------------------
        # BUYER PREFERENCES
        # --------------------------------------------------------
        #
        # Preferences must be deleted before BuyerProfile.
        #

        session.execute(
            delete(BuyerPreferences).where(
                BuyerPreferences.buyer_id.in_(
                    select(BuyerProfile.id).where(
                        BuyerProfile.user_id.in_(
                            select(User.id).where(
                                User.email.like("pytest-%")
                            )
                        )
                    )
                )
            )
        )

        # --------------------------------------------------------
        # BUYER PROFILE
        # --------------------------------------------------------

        session.execute(
            delete(BuyerProfile).where(
                BuyerProfile.user_id.in_(
                    select(User.id).where(
                        User.email.like("pytest-%")
                    )
                )
            )
        )

        # --------------------------------------------------------
        # SELLER PROFILE
        # --------------------------------------------------------

        session.execute(
            delete(SellerProfile).where(
                SellerProfile.user_id.in_(
                    select(User.id).where(
                        User.email.like("pytest-%")
                    )
                )
            )
        )

        # --------------------------------------------------------
        # USERS
        # --------------------------------------------------------

        session.execute(
            delete(User).where(
                User.email.like("pytest-%")
            )
        )

        session.commit()
        session.close()


# ============================================================
# ISOLATE INTAKE FROM OUTBOX / CELERY
# ============================================================


@pytest.fixture(autouse=True)
def disable_outbox_for_intake_tests(monkeypatch):
    """
    These tests are specifically for:

        IntakeService
            ↓
        IntakeRepository
            ↓
        PostgreSQL

    Readiness/outbox/Celery behavior belongs to separate tests.

    The transaction rollback tests below may override the instance
    method again to deliberately simulate a failure after repository
    flush.
    """

    monkeypatch.setattr(
        IntakeService,
        "_create_business_event_if_ready",
        lambda self, business, seller_user_id: None,
    )

    monkeypatch.setattr(
        IntakeService,
        "_create_buyer_event_if_ready",
        lambda self, preferences, profile: None,
    )


# ============================================================
# BASIC DATABASE HELPERS
# ============================================================


def count_buyer_profiles_for_user(
    db: Session,
    user_id,
) -> int:

    return db.scalar(
        select(func.count())
        .select_from(BuyerProfile)
        .where(
            BuyerProfile.user_id == user_id
        )
    )


def count_preferences_for_buyer(
    db: Session,
    buyer_id,
) -> int:

    return db.scalar(
        select(func.count())
        .select_from(BuyerPreferences)
        .where(
            BuyerPreferences.buyer_id == buyer_id
        )
    )


def count_businesses_for_seller(
    db: Session,
    seller_id,
) -> int:

    return db.scalar(
        select(func.count())
        .select_from(Business)
        .where(
            Business.seller_id == seller_id
        )
    )


def reload(
    db: Session,
    model,
    entity_id,
):

    db.expire_all()

    return db.get(
        model,
        entity_id,
    )


# ============================================================
# DOMAIN FIXTURES
# ============================================================


@pytest.fixture
def user(
    db_session: Session,
) -> User:

    user = User(
        id=uuid4(),
        email=f"pytest-{uuid4()}@example.com",
        first_name="Buyer",
        last_name="Test",
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def second_user(
    db_session: Session,
) -> User:

    user = User(
        id=uuid4(),
        email=f"pytest-{uuid4()}@example.com",
        first_name="Other",
        last_name="User",
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def seller(
    db_session: Session,
    user: User,
) -> SellerProfile:

    seller = SellerProfile(
        user_id=user.id,
    )

    db_session.add(seller)
    db_session.commit()
    db_session.refresh(seller)

    return seller


@pytest.fixture
def second_seller(
    db_session: Session,
    second_user: User,
) -> SellerProfile:

    seller = SellerProfile(
        user_id=second_user.id,
    )

    db_session.add(seller)
    db_session.commit()
    db_session.refresh(seller)

    return seller


# ============================================================
# PAYLOAD HELPERS
# ============================================================


def make_business_create(
    **overrides,
) -> BusinessCreate:

    payload = {
        "legal_name": "Test Plumbing LLC",
        "dba": "Test Plumbing",
        "business_type": "llc",
        "industry": "construction_and_trades",
        "sub_industry": "plumbing",
        "business_model": "recurring_service",
        "city": "Austin",
        "county": "Travis",
        "state": "Texas",
        "zip_code": "78701",
    }

    payload.update(overrides)

    return BusinessCreate(
        **payload
    )


# ============================================================
# BUYER PROFILE
# ============================================================


def test_buyer_profile_first_upsert_creates_and_returns_profile(
    db_session: Session,
    user: User,
):
    """
    First upsert should create exactly one BuyerProfile.

    Verify both:
    - returned object
    - persisted database state
    """

    service = IntakeService(
        db_session
    )

    data = BuyerProfileCreate(
        about_me="I want to acquire an operating business.",
        buyer_type="first_time_owner",
        current_industry="Technology",
        current_position="Engineer",
        business_experience_years=4,
        relevant_experience="Backend and AI systems.",
        available_hours_per_week=40,
        city="Austin",
        county="Travis",
        state="Texas",
        zip_code="78701",
    )

    result = service.upsert_buyer_profile(
        user.id,
        data,
    )

    # --------------------------------------------------------
    # RETURN CONTRACT
    # --------------------------------------------------------

    assert isinstance(
        result,
        BuyerProfile,
    )

    assert result.id is not None
    assert result.user_id == user.id

    assert result.about_me == (
        "I want to acquire an operating business."
    )

    assert result.buyer_type == "first_time_owner"
    assert result.current_industry == "Technology"
    assert result.current_position == "Engineer"
    assert result.business_experience_years == 4
    assert result.available_hours_per_week == 40

    assert result.city == "Austin"
    assert result.county == "Travis"
    assert result.state == "Texas"
    assert result.zip_code == "78701"

    # --------------------------------------------------------
    # DATABASE CONTRACT
    # --------------------------------------------------------

    db_session.expire_all()

    rows = list(
        db_session.scalars(
            select(BuyerProfile)
            .where(
                BuyerProfile.user_id == user.id
            )
        ).all()
    )

    assert len(rows) == 1

    persisted = rows[0]

    assert persisted.id == result.id
    assert persisted.user_id == user.id
    assert persisted.current_industry == "Technology"
    assert persisted.city == "Austin"


def test_buyer_profile_second_upsert_updates_same_row(
    db_session: Session,
    user: User,
):
    """
    The second upsert MUST update the existing profile.

    It must NOT:
    - create another row
    - change the profile id
    """

    service = IntakeService(
        db_session
    )

    first = service.upsert_buyer_profile(
        user.id,
        BuyerProfileCreate(
            about_me="Original",
            current_industry="Technology",
            current_position="Engineer",
            city="Austin",
            state="Texas",
        ),
    )

    original_id = first.id

    assert count_buyer_profiles_for_user(
        db_session,
        user.id,
    ) == 1

    second = service.upsert_buyer_profile(
        user.id,
        BuyerProfileUpdate(
            about_me="Updated",
            current_position="Senior Engineer",
        ),
    )

    # --------------------------------------------------------
    # SAME LOGICAL PROFILE
    # --------------------------------------------------------

    assert second.id == original_id
    assert second.user_id == user.id

    assert count_buyer_profiles_for_user(
        db_session,
        user.id,
    ) == 1

    # --------------------------------------------------------
    # UPDATED FIELDS CHANGED
    # --------------------------------------------------------

    assert second.about_me == "Updated"
    assert second.current_position == "Senior Engineer"

    # --------------------------------------------------------
    # UNTOUCHED FIELDS MUST SURVIVE
    # --------------------------------------------------------

    assert second.current_industry == "Technology"
    assert second.city == "Austin"
    assert second.state == "Texas"

    persisted = reload(
        db_session,
        BuyerProfile,
        original_id,
    )

    assert persisted is not None

    assert persisted.about_me == "Updated"
    assert persisted.current_position == "Senior Engineer"

    assert persisted.current_industry == "Technology"
    assert persisted.city == "Austin"
    assert persisted.state == "Texas"


def test_buyer_profile_upsert_requires_real_user(
    db_session: Session,
):
    """
    Repository must not create an orphan BuyerProfile.
    """

    repository = IntakeRepository(
        db_session
    )

    missing_user_id = uuid4()

    with pytest.raises(
        IntakeNotFoundError
    ):
        repository.upsert_buyer_profile(
            missing_user_id,
            BuyerProfileCreate(
                about_me="Should never exist"
            ),
        )

    profile = db_session.scalar(
        select(BuyerProfile)
        .where(
            BuyerProfile.user_id == missing_user_id
        )
    )

    assert profile is None


# ============================================================
# BUYER PREFERENCES
# ============================================================


def test_buyer_preferences_first_upsert_creates_and_returns_preferences(
    db_session: Session,
    user: User,
):
    """
    Buyer preferences should be attached to the user's
    BuyerProfile and persisted.
    """

    service = IntakeService(
        db_session
    )

    profile = service.upsert_buyer_profile(
        user.id,
        BuyerProfileCreate(
            about_me="Buyer"
        ),
    )

    preferences = service.upsert_buyer_preferences(
        user.id,
        BuyerPreferencesUpsert(
            target_industry_preferences=[
                {
                    "industry": "construction_and_trades",
                    "sub_industries": [
                        "plumbing",
                    ],
                }
            ],
            target_business_models=[
                "recurring_service",
            ],
            target_business_types=[
                "llc",
            ],
            maximum_purchase_price=Decimal(
                "1500000.00"
            ),
            minimum_required_sde=Decimal(
                "150000.00"
            ),
            preferred_sde=Decimal(
                "250000.00"
            ),
        ),
    )

    assert isinstance(
        preferences,
        BuyerPreferences,
    )

    assert preferences.id is not None
    assert preferences.buyer_id == profile.id

    assert preferences.maximum_purchase_price == Decimal(
        "1500000.00"
    )

    assert preferences.minimum_required_sde == Decimal(
        "150000.00"
    )

    assert preferences.preferred_sde == Decimal(
        "250000.00"
    )

    db_session.expire_all()

    persisted = db_session.scalar(
        select(BuyerPreferences)
        .where(
            BuyerPreferences.buyer_id == profile.id
        )
    )

    assert persisted is not None

    assert persisted.id == preferences.id
    assert persisted.buyer_id == profile.id

    assert count_preferences_for_buyer(
        db_session,
        profile.id,
    ) == 1


def test_buyer_preferences_second_upsert_updates_same_row_and_preserves_fields(
    db_session: Session,
    user: User,
):
    """
    Critical incremental-onboarding test.

    Sending only one new preference must NOT erase preferences
    that were already saved.
    """

    service = IntakeService(
        db_session
    )

    profile = service.upsert_buyer_profile(
        user.id,
        BuyerProfileCreate(
            about_me="Buyer"
        ),
    )

    first = service.upsert_buyer_preferences(
        user.id,
        BuyerPreferencesUpsert(
            target_industry_preferences=[
                {
                    "industry": "construction_and_trades",
                    "sub_industries": [
                        "plumbing",
                    ],
                }
            ],
            maximum_purchase_price=Decimal(
                "1000000.00"
            ),
            minimum_required_sde=Decimal(
                "100000.00"
            ),
            preferred_sde=Decimal(
                "200000.00"
            ),
        ),
    )

    original_id = first.id

    second = service.upsert_buyer_preferences(
        user.id,
        BuyerPreferencesUpsert(
            maximum_purchase_price=Decimal(
                "1250000.00"
            ),
        ),
    )

    # --------------------------------------------------------
    # MUST BE SAME ROW
    # --------------------------------------------------------

    assert second.id == original_id
    assert second.buyer_id == profile.id

    assert count_preferences_for_buyer(
        db_session,
        profile.id,
    ) == 1

    # --------------------------------------------------------
    # CHANGED FIELD
    # --------------------------------------------------------

    assert second.maximum_purchase_price == Decimal(
        "1250000.00"
    )

    # --------------------------------------------------------
    # PREVIOUS VALUES MUST SURVIVE
    # --------------------------------------------------------

    assert second.minimum_required_sde == Decimal(
        "100000.00"
    )

    assert second.preferred_sde == Decimal(
        "200000.00"
    )

    assert second.target_industry_preferences == [
        {
            "industry": "construction_and_trades",
            "sub_industries": [
                "plumbing",
            ],
        }
    ]

    persisted = reload(
        db_session,
        BuyerPreferences,
        original_id,
    )

    assert persisted is not None

    assert persisted.maximum_purchase_price == Decimal(
        "1250000.00"
    )

    assert persisted.minimum_required_sde == Decimal(
        "100000.00"
    )

    assert persisted.preferred_sde == Decimal(
        "200000.00"
    )


def test_buyer_preferences_require_buyer_profile(
    db_session: Session,
    user: User,
):
    """
    Preferences cannot exist without a BuyerProfile.
    """

    repository = IntakeRepository(
        db_session
    )

    with pytest.raises(
        IntakeNotFoundError,
        match="Create the buyer profile",
    ):
        repository.upsert_buyer_preferences(
            user.id,
            BuyerPreferencesUpsert(
                maximum_purchase_price=Decimal(
                    "1000000.00"
                )
            ),
        )

    profile = db_session.scalar(
        select(BuyerProfile)
        .where(
            BuyerProfile.user_id == user.id
        )
    )

    assert profile is None


# ============================================================
# BUSINESS CREATE
# ============================================================


def test_business_create_persists_and_returns_business(
    db_session: Session,
    user: User,
    seller: SellerProfile,
):
    """
    Service create_business should return the actual persisted
    Business ORM entity.
    """

    service = IntakeService(
        db_session
    )

    key = f"pytest-business-{uuid4()}"

    result = service.create_business(
        user.id,
        make_business_create(),
        key,
    )

    assert isinstance(
        result,
        Business,
    )

    assert result.id is not None
    assert result.seller_id == seller.id
    assert result.idempotency_key == key

    assert result.legal_name == "Test Plumbing LLC"
    assert result.dba == "Test Plumbing"

    assert result.business_type == "llc"
    assert result.industry == "construction_and_trades"
    assert result.sub_industry == "plumbing"
    assert result.business_model == "recurring_service"

    assert result.city == "Austin"
    assert result.county == "Travis"
    assert result.state == "Texas"
    assert result.zip_code == "78701"

    persisted = reload(
        db_session,
        Business,
        result.id,
    )

    assert persisted is not None

    assert persisted.id == result.id
    assert persisted.seller_id == seller.id
    assert persisted.idempotency_key == key

    assert count_businesses_for_seller(
        db_session,
        seller.id,
    ) == 1


def test_business_create_same_idempotency_key_returns_same_business(
    db_session: Session,
    user: User,
    seller: SellerProfile,
):
    """
    Retrying the same logical POST must not create another
    Business.

    Same seller + same Idempotency-Key = same business.
    """

    service = IntakeService(
        db_session
    )

    key = f"pytest-business-{uuid4()}"

    first = service.create_business(
        user.id,
        make_business_create(
            legal_name="Original LLC",
        ),
        key,
    )

    original_id = first.id

    second = service.create_business(
        user.id,
        make_business_create(
            legal_name="This Must Not Replace Original LLC",
        ),
        key,
    )

    # --------------------------------------------------------
    # SAME BUSINESS
    # --------------------------------------------------------

    assert second.id == original_id

    assert count_businesses_for_seller(
        db_session,
        seller.id,
    ) == 1

    # --------------------------------------------------------
    # IDEMPOTENT RETRY DOES NOT BECOME AN UPDATE
    # --------------------------------------------------------

    assert second.legal_name == "Original LLC"

    persisted = reload(
        db_session,
        Business,
        original_id,
    )

    assert persisted is not None
    assert persisted.legal_name == "Original LLC"


def test_same_idempotency_key_can_be_used_by_different_sellers(
    db_session: Session,
    user: User,
    seller: SellerProfile,
    second_user: User,
    second_seller: SellerProfile,
):
    """
    Idempotency is scoped to seller.

    Seller A using key X must not block Seller B from using key X.
    """

    service = IntakeService(
        db_session
    )

    key = f"pytest-shared-{uuid4()}"

    first = service.create_business(
        user.id,
        make_business_create(
            legal_name="Seller A LLC"
        ),
        key,
    )

    second = service.create_business(
        second_user.id,
        make_business_create(
            legal_name="Seller B LLC"
        ),
        key,
    )

    assert first.id != second.id

    assert first.seller_id == seller.id
    assert second.seller_id == second_seller.id

    first_count = count_businesses_for_seller(
        db_session,
        seller.id,
    )

    second_count = count_businesses_for_seller(
        db_session,
        second_seller.id,
    )

    assert first_count == 1
    assert second_count == 1


def test_business_create_requires_seller_profile(
    db_session: Session,
    user: User,
):
    """
    User existing is not enough.

    Business creation requires SellerProfile.
    """

    service = IntakeService(
        db_session
    )

    key = f"pytest-business-{uuid4()}"

    with pytest.raises(
        IntakeNotFoundError,
        match="Create the seller profile",
    ):
        service.create_business(
            user.id,
            make_business_create(),
            key,
        )

    persisted = db_session.scalar(
        select(Business)
        .where(
            Business.idempotency_key == key
        )
    )

    assert persisted is None


# ============================================================
# BUSINESS UPDATE
# ============================================================


def test_business_update_changes_requested_fields_and_preserves_rest(
    db_session: Session,
    user: User,
    seller: SellerProfile,
):
    """
    BusinessUpdate is PATCH-like.

    Only explicitly supplied fields should change.
    """

    service = IntakeService(
        db_session
    )

    business = service.create_business(
        user.id,
        make_business_create(
            legal_name="Original Plumbing LLC",
            city="Austin",
            state="Texas",
            zip_code="78701",
        ),
        f"pytest-business-{uuid4()}",
    )

    original_id = business.id
    original_seller_id = business.seller_id
    original_key = business.idempotency_key

    updated = service.update_business(
        user.id,
        business.id,
        BusinessUpdate(
            legal_name="Updated Plumbing LLC",
            asking_price=Decimal(
                "850000.00"
            ),
            sde=Decimal(
                "225000.00"
            ),
        ),
    )

    # --------------------------------------------------------
    # SAME BUSINESS
    # --------------------------------------------------------

    assert updated.id == original_id
    assert updated.seller_id == original_seller_id
    assert updated.idempotency_key == original_key

    assert count_businesses_for_seller(
        db_session,
        seller.id,
    ) == 1

    # --------------------------------------------------------
    # REQUESTED FIELDS CHANGED
    # --------------------------------------------------------

    assert updated.legal_name == "Updated Plumbing LLC"

    assert updated.asking_price == Decimal(
        "850000.00"
    )

    assert updated.sde == Decimal(
        "225000.00"
    )

    # --------------------------------------------------------
    # UNTOUCHED FIELDS SURVIVE
    # --------------------------------------------------------

    assert updated.dba == "Test Plumbing"
    assert updated.business_type == "llc"

    assert updated.industry == (
        "construction_and_trades"
    )

    assert updated.sub_industry == "plumbing"

    assert updated.business_model == (
        "recurring_service"
    )

    assert updated.city == "Austin"
    assert updated.county == "Travis"
    assert updated.state == "Texas"
    assert updated.zip_code == "78701"

    # --------------------------------------------------------
    # VERIFY FROM DATABASE, NOT JUST IN-MEMORY OBJECT
    # --------------------------------------------------------

    persisted = reload(
        db_session,
        Business,
        original_id,
    )

    assert persisted is not None

    assert persisted.legal_name == (
        "Updated Plumbing LLC"
    )

    assert persisted.asking_price == Decimal(
        "850000.00"
    )

    assert persisted.sde == Decimal(
        "225000.00"
    )

    assert persisted.city == "Austin"
    assert persisted.state == "Texas"


def test_business_update_rejects_different_seller(
    db_session: Session,
    user: User,
    seller: SellerProfile,
    second_user: User,
    second_seller: SellerProfile,
):
    """
    Seller B must not be able to update Seller A's business.
    """

    service = IntakeService(
        db_session
    )

    business = service.create_business(
        user.id,
        make_business_create(),
        f"pytest-business-{uuid4()}",
    )

    original_name = business.legal_name

    with pytest.raises(
        IntakeNotFoundError,
        match="Business does not exist for this seller",
    ):
        service.update_business(
            second_user.id,
            business.id,
            BusinessUpdate(
                legal_name="Hijacked Business"
            ),
        )

    persisted = reload(
        db_session,
        Business,
        business.id,
    )

    assert persisted is not None

    assert persisted.seller_id == seller.id
    assert persisted.seller_id != second_seller.id

    assert persisted.legal_name == original_name


def test_business_update_rejects_missing_business(
    db_session: Session,
    user: User,
    seller: SellerProfile,
):
    """
    Updating a nonexistent business must fail.
    """

    service = IntakeService(
        db_session
    )

    missing_business_id = uuid4()

    with pytest.raises(
        IntakeNotFoundError,
        match="Business does not exist for this seller",
    ):
        service.update_business(
            user.id,
            missing_business_id,
            BusinessUpdate(
                legal_name="Does Not Exist"
            ),
        )

    persisted = db_session.get(
        Business,
        missing_business_id,
    )

    assert persisted is None


# ============================================================
# TRANSACTION BEHAVIOR
# ============================================================


def test_create_business_rolls_back_if_service_fails_after_repository_flush(
    db_session: Session,
    user: User,
    seller: SellerProfile,
    monkeypatch,
):
    """
    Repository.create_business() performs a flush but does not commit.

    Therefore if something fails later inside IntakeService,
    the entire business creation must disappear after rollback.

    This proves the repository + service transaction boundary
    actually works.
    """

    service = IntakeService(
        db_session
    )

    def explode_after_business_creation(
        business,
        seller_user_id,
    ):
        raise RuntimeError(
            "simulated downstream failure"
        )

    monkeypatch.setattr(
        service,
        "_create_business_event_if_ready",
        explode_after_business_creation,
    )

    key = f"pytest-rollback-{uuid4()}"

    with pytest.raises(
        RuntimeError,
        match="simulated downstream failure",
    ):
        service.create_business(
            user.id,
            make_business_create(),
            key,
        )

    # Start inspection from clean session state.
    db_session.expire_all()

    persisted = db_session.scalar(
        select(Business)
        .where(
            Business.idempotency_key == key
        )
    )

    assert persisted is None


def test_update_business_rolls_back_if_service_fails_after_repository_flush(
    db_session: Session,
    user: User,
    seller: SellerProfile,
    monkeypatch,
):
    """
    Same transaction guarantee for updates.

    Repository may mutate + flush the ORM entity.

    If the service fails before commit, rollback must restore
    the previous database state.
    """

    service = IntakeService(
        db_session
    )

    business = service.create_business(
        user.id,
        make_business_create(
            legal_name="Original LLC"
        ),
        f"pytest-business-{uuid4()}",
    )

    business_id = business.id

    def explode_after_update(
        business,
        seller_user_id,
    ):
        raise RuntimeError(
            "simulated downstream failure"
        )

    monkeypatch.setattr(
        service,
        "_create_business_event_if_ready",
        explode_after_update,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated downstream failure",
    ):
        service.update_business(
            user.id,
            business_id,
            BusinessUpdate(
                legal_name="Should Roll Back"
            ),
        )

    db_session.expire_all()

    persisted = db_session.get(
        Business,
        business_id,
    )

    assert persisted is not None

    assert persisted.legal_name == "Original LLC"


def test_buyer_profile_service_rolls_back_repository_write_on_commit_failure(
    db_session: Session,
    user: User,
    monkeypatch,
):
    """
    Verify IntakeService does not leave a flushed BuyerProfile
    hanging when commit fails.
    """

    service = IntakeService(
        db_session
    )

    real_commit = db_session.commit

    def failing_commit():
        raise RuntimeError(
            "simulated commit failure"
        )

    monkeypatch.setattr(
        db_session,
        "commit",
        failing_commit,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated commit failure",
    ):
        service.upsert_buyer_profile(
            user.id,
            BuyerProfileCreate(
                about_me="Must be rolled back"
            ),
        )

    # Restore commit so the fixture can later clean up normally.
    monkeypatch.setattr(
        db_session,
        "commit",
        real_commit,
    )

    db_session.expire_all()

    profile = db_session.scalar(
        select(BuyerProfile)
        .where(
            BuyerProfile.user_id == user.id
        )
    )

    assert profile is None