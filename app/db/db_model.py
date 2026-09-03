from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.db_enum import (
    BuyerType,
    UserStatus,
    VerificationStatus,
    DealPreference,
    RealEstatePreference,
    FundingSource,
    BusinessStatus,
    DocumentType,
    StorageProvider,
    MatchStatus,
    LenderApprovedStatus
)


# ============================================================
# BASE
# ============================================================

class Base(DeclarativeBase):
    pass

# ============================================================
# USERS
# ============================================================

class User(Base):
    """
    Application-level user record.

    Authentication is handled by Supabase Auth.

    User.id MUST match auth.users.id.
    We intentionally do not generate this UUID inside SQLAlchemy.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(320),
        unique=True,
        nullable=True,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        unique=True,
        nullable=True,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[UserStatus] = mapped_column(
        String(20),
        default=UserStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    buyer_profile: Mapped["BuyerProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    seller_profile: Mapped["SellerProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ============================================================
# BUYER PROFILE
# ============================================================

class BuyerProfile(Base):
    """
    Identity and experience information about the buyer.

    Matching preferences live in BuyerPreferences.
    Financial capability / verification lives in BuyerFinancials.
    """

    __tablename__ = "buyer_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        # Application-generated profile UUID.
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    buyer_type: Mapped[BuyerType] = mapped_column(
        String(40),
        nullable=False,
    )

    current_industry: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    current_position: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    business_experience_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    relevant_experience: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    available_hours_per_week: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    county: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    zip_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    verification_status: Mapped[VerificationStatus] = mapped_column(
        String(30),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="buyer_profile",
    )

    preferences: Mapped["BuyerPreferences | None"] = relationship(
        back_populates="buyer",
        uselist=False,
        cascade="all, delete-orphan",
    )

    financials: Mapped["BuyerFinancials | None"] = relationship(
        back_populates="buyer",
        uselist=False,
        cascade="all, delete-orphan",
    )

    matches: Mapped[list["Match"]] = relationship(
        back_populates="buyer",
        foreign_keys="Match.buyer_id",
    )

    __table_args__ = (
        CheckConstraint(
            "business_experience_years IS NULL "
            "OR business_experience_years >= 0",
            name="ck_buyer_experience_nonnegative",
        ),
        CheckConstraint(
            "available_hours_per_week IS NULL "
            "OR available_hours_per_week >= 0",
            name="ck_buyer_available_hours_nonnegative",
        ),
    )


# ============================================================
# BUYER PREFERENCES
# ============================================================

class BuyerPreferences(Base):
    """
    Everything the buyer specifies for matching.

    This table contains preferences, NOT proof of financial capability.
    """

    __tablename__ = "buyer_preferences"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    buyer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("buyer_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Industry / Geography
    # --------------------------------------------------------

    target_industries: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    target_locations: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # --------------------------------------------------------
    # Purchase Price
    # --------------------------------------------------------

    maximum_purchase_price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    # --------------------------------------------------------
    # SDE
    # --------------------------------------------------------

    minimum_required_sde: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    preferred_sde: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    # --------------------------------------------------------
    # ARR
    # --------------------------------------------------------

    minimum_required_arr: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    preferred_arr: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    # --------------------------------------------------------
    # Owner Involvement
    # --------------------------------------------------------

    preferred_owner_hours_per_week: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # --------------------------------------------------------
    # Transition Training
    # --------------------------------------------------------

    required_transition_training_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # --------------------------------------------------------
    # Deal Preference
    # --------------------------------------------------------

    deal_preference: Mapped[DealPreference | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # --------------------------------------------------------
    # Additional Buyer Preferences
    # --------------------------------------------------------

    real_estate_preference: Mapped[RealEstatePreference | None] = mapped_column(
        String(20),
        nullable=True,
    )

    minimum_years_in_operation: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    accepts_customer_concentration_above_25_percent: Mapped[
        bool
    ] = mapped_column(
        Boolean,
        nullable=False,
    )

    preferred_acquisition_timeline: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # --------------------------------------------------------
    # Timestamps
    # --------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    buyer: Mapped["BuyerProfile"] = relationship(
        back_populates="preferences",
    )

    # --------------------------------------------------------
    # Database Constraints
    # --------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "maximum_purchase_price IS NULL "
            "OR maximum_purchase_price >= 0",
            name="ck_buyer_max_price_nonnegative",
        ),

        CheckConstraint(
            "minimum_required_sde IS NULL "
            "OR minimum_required_sde >= 0",
            name="ck_buyer_min_sde_nonnegative",
        ),

        CheckConstraint(
            """
            minimum_required_sde IS NULL
            OR preferred_sde IS NULL
            OR minimum_required_sde <= preferred_sde
            """,
            name="ck_buyer_sde_min_lte_preferred",
        ),

        CheckConstraint(
            """
            minimum_required_arr IS NULL
            OR preferred_arr IS NULL
            OR minimum_required_arr <= preferred_arr
            """,
            name="ck_buyer_arr_min_lte_preferred",
        ),

        CheckConstraint(
            "preferred_sde IS NULL "
            "OR preferred_sde >= 0",
            name="ck_buyer_preferred_sde_nonnegative",
        ),

        CheckConstraint(
            "minimum_required_arr IS NULL "
            "OR minimum_required_arr >= 0",
            name="ck_buyer_min_arr_nonnegative",
        ),

        CheckConstraint(
            "preferred_arr IS NULL "
            "OR preferred_arr >= 0",
            name="ck_buyer_preferred_arr_nonnegative",
        ),

        CheckConstraint(
            "preferred_owner_hours_per_week IS NULL "
            "OR preferred_owner_hours_per_week >= 0",
            name="ck_buyer_owner_hours_nonnegative",
        ),

        CheckConstraint(
            "required_transition_training_days IS NULL "
            "OR required_transition_training_days >= 0",
            name="ck_buyer_training_days_nonnegative",
        ),
    )


# ============================================================
# BUYER FINANCIALS
# ============================================================

class BuyerFinancials(Base):
    """
    Financial capability and financial verification for a buyer.

    This table answers:

        "Can this buyer actually fund the transaction?"

    Matching preferences such as maximum purchase price,
    minimum SDE, and preferred SDE belong to BuyerPreferences.

    Actual documents are NOT stored here.

    The document itself lives in Cloudflare R2.
    The Document table stores metadata and the R2 object reference.
    """

    __tablename__ = "buyer_financials"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    buyer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "buyer_profiles.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Funding
    # --------------------------------------------------------

    funding_source: Mapped[FundingSource | None] = mapped_column(
        String(40),
        nullable=True,
    )

    reported_cash_available: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    verified_cash_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    financing_requested_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    financing_approved_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    lender_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    lender_approval_status: Mapped[LenderApprovedStatus | None] = mapped_column(
        String(30),
        default=LenderApprovedStatus.PENDING,
        nullable=True,
        index=True,
    )

    # --------------------------------------------------------
    # Verification
    # --------------------------------------------------------

    verification_status: Mapped[VerificationStatus] = mapped_column(
        String(30),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )

    verification_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    provider_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    provider_response: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    buyer: Mapped["BuyerProfile"] = relationship(
        back_populates="financials",
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="buyer_financials",
        cascade="all, delete-orphan",
        foreign_keys="Document.buyer_financials_id",
    )

    __table_args__ = (
        CheckConstraint(
            "reported_cash_available IS NULL OR reported_cash_available >= 0",
            name="ck_buyer_cash_nonnegative",
        ),
        CheckConstraint(
            "verified_cash_amount IS NULL "
            "OR verified_cash_amount >= 0",
            name="ck_buyer_verified_cash_nonnegative",
        ),
        CheckConstraint(
            "financing_requested_amount IS NULL "
            "OR financing_requested_amount >= 0",
            name="ck_buyer_financing_requested_nonnegative",
        ),
        CheckConstraint(
            "financing_approved_amount IS NULL "
            "OR financing_approved_amount >= 0",
            name="ck_buyer_financing_approved_nonnegative",
        ),
    )


# ============================================================
# SELLER PROFILE
# ============================================================

class SellerProfile(Base):
    """
    Seller identity / seller-level information.

    Businesses belong to the seller, but the business itself
    contains the information specific to the asset being sold.
    """

    __tablename__ = "seller_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    verification_status: Mapped[VerificationStatus] = mapped_column(
        String(30),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="seller_profile",
    )

    businesses: Mapped[list["Business"]] = relationship(
        back_populates="seller",
        cascade="all, delete-orphan",
    )


# ============================================================
# BUSINESS
# ============================================================

class Business(Base):
    """
    The actual business / asset being sold.

    Everything required by the V1 matching engine lives here
    on the seller side:
        - industry
        - geography
        - asking price
        - SDE
        - arr
        - customer_concentration
        - owner involvement
        - transition training
        - deal preference
        - preferred sale timeline
    """

    __tablename__ = "businesses"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    seller_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("seller_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    legal_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    dba: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    business_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    industry: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Geography
    # --------------------------------------------------------

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    county: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    zip_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # --------------------------------------------------------
    # Business Attributes
    # --------------------------------------------------------

    years_in_operation: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    number_of_locations: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    number_of_routes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # --------------------------------------------------------
    # Financial / Business Metrics
    # --------------------------------------------------------

    arr: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        index=True,
    )

    customer_concentration: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # --------------------------------------------------------
    # Matching Inputs
    # --------------------------------------------------------

    asking_price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        index=True,
    )

    sde: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        index=True,
    )

    owner_involvement_hours_per_week: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    transition_training_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    # Seller can specify a fixed number of days or
    # "as long as you need" at the application/schema level.
    # which would translate to infinite days, always exceeding buyer prefered days

    deal_preference: Mapped[DealPreference | None] = mapped_column(
        String(20),
        nullable=True,
    )

    preferred_sale_timeline: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # --------------------------------------------------------
    # Verification / Lifecycle
    # --------------------------------------------------------

    verification_status: Mapped[VerificationStatus] = mapped_column(
        String(30),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )

    status: Mapped[BusinessStatus] = mapped_column(
        String(30),
        default=BusinessStatus.DRAFT,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    seller: Mapped["SellerProfile"] = relationship(
        back_populates="businesses",
    )

    financials: Mapped["BusinessFinancials | None"] = relationship(
        back_populates="business",
        uselist=False,
        cascade="all, delete-orphan",
    )

    matches: Mapped[list["Match"]] = relationship(
        back_populates="business",
        foreign_keys="Match.business_id",
    )

    # --------------------------------------------------------
    # Database Constraints
    # --------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "asking_price IS NULL OR asking_price >= 0",
            name="ck_business_asking_price_nonnegative",
        ),

        CheckConstraint(
            "sde IS NULL OR sde >= 0",
            name="ck_business_sde_nonnegative",
        ),

        CheckConstraint(
            "arr IS NULL OR arr >= 0",
            name="ck_business_arr_nonnegative",
        ),

        CheckConstraint(
            "customer_concentration IS NULL "
            "OR (customer_concentration >= 0 "
            "AND customer_concentration <= 100)",
            name="ck_business_customer_concentration_percentage",
        ),

        CheckConstraint(
            "owner_involvement_hours_per_week IS NULL "
            "OR owner_involvement_hours_per_week >= 0",
            name="ck_business_owner_hours_nonnegative",
        ),

        CheckConstraint(
            "transition_training_days IS NULL "
            "OR transition_training_days >= 0",
            name="ck_business_training_days_nonnegative",
        ),

        CheckConstraint(
            "years_in_operation IS NULL OR years_in_operation >= 0",
            name="ck_business_years_nonnegative",
        ),

        CheckConstraint(
            "number_of_locations IS NULL OR number_of_locations >= 0",
            name="ck_business_locations_nonnegative",
        ),

        CheckConstraint(
            "number_of_routes IS NULL OR number_of_routes >= 0",
            name="ck_business_routes_nonnegative",
        ),
    )

# ============================================================
# BUSINESS FINANCIALS
# ============================================================


class BusinessFinancials(Base):
    """
    Financial information and financial verification for a business.

    The actual business document/file is stored in Cloudflare R2.

    This table stores:
        - financial values
        - verification information
        - provider information

    The Document table stores references to supporting documents.
    """

    __tablename__ = "business_financials"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "businesses.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Financial Information
    # --------------------------------------------------------

    verified_arr: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    verified_sde: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    verified_ebitda: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    revenue_growth_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    verified_recurring_revenue_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    verified_customer_concentration: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    inventory_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    accounts_receivable: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    owner_add_backs: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    financial_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # --------------------------------------------------------
    # Verification
    # --------------------------------------------------------

    verification_status: Mapped[VerificationStatus] = mapped_column(
        String(30),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )

    verification_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    provider_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    provider_response: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    business: Mapped["Business"] = relationship(
        back_populates="financials",
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="business_financials",
        cascade="all, delete-orphan",
        foreign_keys="Document.business_financials_id",
    )

    __table_args__ = (
        CheckConstraint(
            "verified_arr IS NULL OR verified_arr >= 0",
            name="ck_business_financials_arr_nonnegative",
        ),
        CheckConstraint(
            "verified_sde IS NULL OR verified_sde >= 0",
            name="ck_business_financials_sde_nonnegative",
        ),
        CheckConstraint(
            "verified_ebitda IS NULL OR verified_ebitda >= 0",
            name="ck_business_financials_ebitda_nonnegative",
        ),
        CheckConstraint(
            "inventory_value IS NULL OR inventory_value >= 0",
            name="ck_business_financials_inventory_nonnegative",
        ),
        CheckConstraint(
            "accounts_receivable IS NULL "
            "OR accounts_receivable >= 0",
            name="ck_business_financials_ar_nonnegative",
        ),
        CheckConstraint(
            "verified_recurring_revenue_percentage IS NULL "
            "OR verified_recurring_revenue_percentage BETWEEN 0 AND 100",
            name="ck_business_financials_recurring_revenue_percentage",
        ),
        CheckConstraint(
            "verified_customer_concentration IS NULL "
            "OR verified_customer_concentration BETWEEN 0 AND 100",
            name="ck_business_financials_customer_percentage",
        ),
    )




# ============================================================
# DOCUMENTS
# ============================================================

class Document(Base):
    """
    Metadata for a document stored in Cloudflare R2.

    PostgreSQL NEVER stores the actual document bytes.

    Example:

        R2 bucket:
            matchbook-private

        R2 object:
            buyers/<buyer_id>/financials/bank_statement.pdf

        PostgreSQL:
            bucket_name = "matchbook-private"
            object_key = "buyers/<buyer_id>/financials/bank_statement.pdf"

    Ownership is explicit.

    A document belongs either to:
        - BuyerFinancials
        - BusinessFinancials

    The actual file remains in R2.
    """

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # --------------------------------------------------------
    # Explicit ownership
    # --------------------------------------------------------

    buyer_financials_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "buyer_financials.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    business_financials_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "business_financials.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    # --------------------------------------------------------
    # Document information
    # --------------------------------------------------------

    document_type: Mapped[DocumentType] = mapped_column(
        String(50),
        nullable=False,
    )

    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # --------------------------------------------------------
    # R2 location
    # --------------------------------------------------------

    storage_provider: Mapped[StorageProvider] = mapped_column(
        String(30),
        default=StorageProvider.CLOUDFLARE_R2,
        nullable=False,
    )

    bucket_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # --------------------------------------------------------
    # Verification
    # --------------------------------------------------------

    verification_status: Mapped[VerificationStatus] = mapped_column(
        String(30),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )

    verification_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    provider_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --------------------------------------------------------
    # Additional metadata
    # --------------------------------------------------------

    document_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    buyer_financials: Mapped["BuyerFinancials | None"] = relationship(
        back_populates="documents",
        foreign_keys=[buyer_financials_id],
    )

    business_financials: Mapped["BusinessFinancials | None"] = relationship(
        back_populates="documents",
        foreign_keys=[business_financials_id],
    )

    __table_args__ = (
        # A document must have exactly ONE owner.
        CheckConstraint(
            """
            (
                buyer_financials_id IS NOT NULL
                AND business_financials_id IS NULL
            )
            OR
            (
                buyer_financials_id IS NULL
                AND business_financials_id IS NOT NULL
            )
            """,
            name="ck_document_exactly_one_owner",
        ),

        CheckConstraint(
            "file_size IS NULL OR file_size >= 0",
            name="ck_document_file_size_nonnegative",
        ),

        UniqueConstraint(
            "bucket_name",
            "object_key",
            name="uq_document_r2_object",
        ),
    )


# ============================================================
# MATCH
# ============================================================

class Match(Base):
    """
    Represents a buyer <-> business match.

    The Match table also owns the lifecycle of the relationship
    after a successful match.
    """

    __tablename__ = "matches"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    buyer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("buyer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Final Match Score
    # --------------------------------------------------------

    score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )

    # --------------------------------------------------------
    # Individual Dimension Scores
    # --------------------------------------------------------

    industry_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    geography_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    price_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    sde_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    arr_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    owner_involvement_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    customer_concentration_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    transition_training_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    deal_preference_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    # --------------------------------------------------------
    # Weighted Contributions
    # --------------------------------------------------------

    industry_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    geography_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    arr_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    price_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    sde_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    owner_involvement_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    customer_concentration_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    transition_training_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    deal_preference_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5),
        nullable=True,
    )

    # --------------------------------------------------------
    # Explainability
    # --------------------------------------------------------

    score_breakdown: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------

    status: Mapped[MatchStatus] = mapped_column(
        String(30),
        default=MatchStatus.MATCHED,
        nullable=False,
        index=True,
    )

    matching_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    buyer: Mapped["BuyerProfile"] = relationship(
        back_populates="matches",
        foreign_keys=[buyer_id],
    )

    business: Mapped["Business"] = relationship(
        back_populates="matches",
        foreign_keys=[business_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "buyer_id",
            "business_id",
            name="uq_buyer_business_match",
        ),

        Index(
            "ix_matches_buyer_status",
            "buyer_id",
            "status",
        ),

        Index(
            "ix_matches_business_status",
            "business_id",
            "status",
        ),

        CheckConstraint(
            "score BETWEEN 0 AND 1",
            name="ck_match_score_range",
        ),

        CheckConstraint(
            "industry_score IS NULL OR industry_score BETWEEN 0 AND 1",
            name="ck_match_industry_score_range",
        ),

        CheckConstraint(
            "arr_score IS NULL OR arr_score BETWEEN 0 AND 1",
            name="ck_match_arr_score_range",
        ),

        CheckConstraint(
            "geography_score IS NULL OR geography_score BETWEEN 0 AND 1",
            name="ck_match_geography_score_range",
        ),

        CheckConstraint(
            "price_score IS NULL OR price_score BETWEEN 0 AND 1",
            name="ck_match_price_score_range",
        ),

        CheckConstraint(
            "sde_score IS NULL OR sde_score BETWEEN 0 AND 1",
            name="ck_match_sde_score_range",
        ),

        CheckConstraint(
            "owner_involvement_score IS NULL "
            "OR owner_involvement_score BETWEEN 0 AND 1",
            name="ck_match_owner_score_range",
        ),

        CheckConstraint(
            "customer_concentration_score IS NULL "
            "OR customer_concentration_score BETWEEN 0 AND 1",
            name="ck_match_customer_concentration_score_range",
        ),

        CheckConstraint(
            "transition_training_score IS NULL "
            "OR transition_training_score BETWEEN 0 AND 1",
            name="ck_match_training_score_range",
        ),

        CheckConstraint(
            "deal_preference_score IS NULL "
            "OR deal_preference_score BETWEEN 0 AND 1",
            name="ck_match_deal_score_range",
        ),
    )

