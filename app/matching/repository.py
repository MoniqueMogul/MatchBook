from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.db_enum import BusinessStatus, MatchStatus
from app.db.db_model import (
    Business,
    BuyerPreferences,
    Match,
)

from app.matching.config import (
    MATCHING_VERSION,
    PRICE_TOLERANCE,
)

from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
    MatchEvaluation,
)


class MatchingRepositoryError(Exception):
    """
    Base exception for Matching Engine repository errors.
    """


class MatchingDataNotFoundError(MatchingRepositoryError):
    """
    Raised when a required database record cannot be found.
    """


class MatchingDataIncompleteError(MatchingRepositoryError):
    """
    Raised when a database record exists but does not contain
    the fields required by the V1 Matching Engine.
    """


def _enum_value(value: Any) -> Any:
    """
    Convert Enum values to their persisted/string values.
    """
    if isinstance(value, Enum):
        return value.value

    return value


def _score_decimal(
    value: float | None,
) -> Decimal | None:
    """
    Convert an in-memory floating-point score into Decimal
    for SQLAlchemy Numeric persistence.
    """
    if value is None:
        return None

    return Decimal(
        str(
            round(
                value,
                10,
            )
        )
    )


# ============================================================
# DATABASE LOOKUPS
# ============================================================


def get_buyer_preferences(
    session: Session,
    buyer_id: UUID,
) -> BuyerPreferences:
    """
    Load BuyerPreferences for one buyer.
    """

    statement = (
        select(
            BuyerPreferences
        )
        .where(
            BuyerPreferences.buyer_id
            == buyer_id
        )
    )

    preferences = session.scalar(
        statement
    )

    if preferences is None:
        raise MatchingDataNotFoundError(
            "No BuyerPreferences found "
            f"for buyer_id={buyer_id}"
        )

    return preferences


def get_business(
    session: Session,
    business_id: UUID,
) -> Business:
    """
    Load one business record.
    """

    statement = (
        select(
            Business
        )
        .where(
            Business.id
            == business_id
        )
    )

    business = session.scalar(
        statement
    )

    if business is None:
        raise MatchingDataNotFoundError(
            "No Business found "
            f"for business_id={business_id}"
        )

    return business


def get_candidate_businesses(
    session: Session,
    preferences: BuyerPreferences,
) -> list[Business]:
    """
    Retrieve candidate businesses using inexpensive database-level
    hard constraints before detailed Matching Engine evaluation.

    PostgreSQL remains the source of truth.

    Current pre-filters:
        - Active business
        - Industry
        - Maximum purchase price + tolerance
        - Minimum SDE
        - Minimum ARR
        - Minimum years in operation

    Geography is still evaluated by the pure eligibility layer
    because target_locations is structured JSON data.
    """

    statement = (
        select(
            Business
        )
        .where(
            Business.status
            == BusinessStatus.ACTIVE
        )
    )

    # --------------------------------------------------------
    # INDUSTRY
    # --------------------------------------------------------

    if preferences.target_industries:
        industries = [
            str(
                industry
            ).strip()
            for industry
            in preferences.target_industries
            if str(
                industry
            ).strip()
        ]

        if industries:
            statement = (
                statement.where(
                    Business.industry.in_(
                        industries
                    )
                )
            )

    # --------------------------------------------------------
    # PURCHASE PRICE
    # --------------------------------------------------------

    if (
        preferences.maximum_purchase_price
        is not None
    ):
        tolerance = Decimal(
            str(
                PRICE_TOLERANCE
            )
        )

        absolute_ceiling = (
            preferences.maximum_purchase_price
            * (
                Decimal("1")
                + tolerance
            )
        )

        statement = (
            statement.where(
                Business.asking_price.is_not(
                    None
                ),
                Business.asking_price
                <= absolute_ceiling,
            )
        )

    # --------------------------------------------------------
    # MINIMUM SDE
    # --------------------------------------------------------

    if (
        preferences.minimum_required_sde
        is not None
    ):
        statement = (
            statement.where(
                Business.sde.is_not(
                    None
                ),
                Business.sde
                >= preferences.minimum_required_sde,
            )
        )

    # --------------------------------------------------------
    # MINIMUM ARR
    # --------------------------------------------------------

    if (
        preferences.minimum_required_arr
        is not None
    ):
        statement = (
            statement.where(
                Business.arr.is_not(
                    None
                ),
                Business.arr
                >= preferences.minimum_required_arr,
            )
        )

    # --------------------------------------------------------
    # MINIMUM YEARS IN OPERATION
    # --------------------------------------------------------

    if (
        preferences.minimum_years_in_operation
        is not None
    ):
        statement = (
            statement.where(
                Business.years_in_operation.is_not(
                    None
                ),
                Business.years_in_operation
                >= preferences.minimum_years_in_operation,
            )
        )

    result = session.scalars(
        statement
    )

    return list(
        result.all()
    )


# ============================================================
# DATABASE MODEL -> MATCHING ENGINE INPUT
# ============================================================


def build_buyer_match_input(
    preferences: BuyerPreferences,
) -> BuyerMatchInput:
    """
    Convert BuyerPreferences into the pure Matching Engine input.

    Required scoring fields are validated explicitly rather than
    silently inventing values.
    """

    missing: list[str] = []

    if preferences.preferred_sde is None:
        missing.append(
            "preferred_sde"
        )

    if (
        preferences.preferred_owner_hours_per_week
        is None
    ):
        missing.append(
            "preferred_owner_hours_per_week"
        )

    if (
        preferences.required_transition_training_days
        is None
    ):
        missing.append(
            "required_transition_training_days"
        )

    if preferences.deal_preference is None:
        missing.append(
            "deal_preference"
        )

    if preferences.preferred_arr is None:
        missing.append(
            "preferred_arr"
        )

    if (
        preferences.accepts_customer_concentration_above_25_percent
        is None
    ):
        missing.append(
            "accepts_customer_concentration_above_25_percent"
        )

    if missing:
        raise MatchingDataIncompleteError(
            "BuyerPreferences is not ready "
            "for V1 matching. Missing fields: "
            + ", ".join(
                missing
            )
        )

    minimum_arr = (
        preferences.minimum_required_arr
        if (
            preferences.minimum_required_arr
            is not None
        )
        else Decimal("0")
    )

    return BuyerMatchInput(
        buyer_id=(
            preferences.buyer_id
        ),

        target_industries=(
            preferences.target_industries
        ),

        target_locations=(
            preferences.target_locations
        ),

        maximum_purchase_price=(
            preferences.maximum_purchase_price
        ),

        minimum_sde=(
            preferences.minimum_required_sde
        ),

        preferred_sde=(
            preferences.preferred_sde
        ),

        preferred_owner_hours=float(
            preferences.preferred_owner_hours_per_week
        ),

        required_training_days=float(
            preferences.required_transition_training_days
        ),

        deal_preference=str(
            _enum_value(
                preferences.deal_preference
            )
        ),

        minimum_arr=(
            minimum_arr
        ),

        preferred_arr=(
            preferences.preferred_arr
        ),

        accepts_customer_concentration_above_25_percent=bool(
            preferences.accepts_customer_concentration_above_25_percent
        ),

        minimum_years_in_operation=(
            preferences.minimum_years_in_operation
        ),
    )


def build_business_match_input(
    business: Business,
) -> BusinessMatchInput:
    """
    Convert Business into the pure Matching Engine input.
    """

    missing: list[str] = []

    if business.asking_price is None:
        missing.append(
            "asking_price"
        )

    if business.sde is None:
        missing.append(
            "sde"
        )

    if business.arr is None:
        missing.append(
            "arr"
        )

    if (
        business.owner_involvement_hours_per_week
        is None
    ):
        missing.append(
            "owner_involvement_hours_per_week"
        )

    if (
        business.transition_training_days
        is None
    ):
        missing.append(
            "transition_training_days"
        )

    if business.deal_preference is None:
        missing.append(
            "deal_preference"
        )

    if (
        business.customer_concentration
        is None
    ):
        missing.append(
            "customer_concentration"
        )

    if missing:
        raise MatchingDataIncompleteError(
            "Business is not ready for "
            "V1 matching. "
            f"business_id={business.id}. "
            "Missing fields: "
            + ", ".join(
                missing
            )
        )

    return BusinessMatchInput(
        business_id=(
            business.id
        ),

        industry=(
            business.industry
        ),

        city=(
            business.city
        ),

        county=(
            business.county
        ),

        state=(
            business.state
        ),

        asking_price=(
            business.asking_price
        ),

        sde=(
            business.sde
        ),

        owner_hours=float(
            business.owner_involvement_hours_per_week
        ),

        transition_training_days=float(
            business.transition_training_days
        ),

        deal_preference=str(
            _enum_value(
                business.deal_preference
            )
        ),

        arr=(
            business.arr
        ),

        largest_customer_percent=float(
            business.customer_concentration
        ),

        years_in_operation=(
            business.years_in_operation
        ),
    )


# ============================================================
# EXPLAINABILITY
# ============================================================


def build_score_breakdown(
    evaluation: MatchEvaluation,
) -> dict[str, Any]:
    """
    Build JSON-safe explainability information for
    Match.score_breakdown.
    """

    dimensions: dict[
        str,
        Any,
    ] = {}

    for (
        name,
        dimension,
    ) in evaluation.dimensions.items():

        dimensions[
            name
        ] = {
            "score": round(
                dimension.score,
                10,
            ),
            "weight": round(
                dimension.weight,
                10,
            ),
            "contribution": round(
                dimension.contribution,
                10,
            ),
        }

    return {
        "matching_version": (
            MATCHING_VERSION
        ),
        "eligible": (
            evaluation.eligible
        ),
        "failed_constraints": list(
            evaluation.failed_constraints
        ),
        "score": (
            evaluation.score
        ),
        "percentage": (
            evaluation.percentage
        ),
        "meets_threshold": (
            evaluation.meets_threshold
        ),
        "dimensions": (
            dimensions
        ),
    }


# ============================================================
# MATCH LOOKUP
# ============================================================


def get_existing_match(
    session: Session,
    buyer_id: UUID,
    business_id: UUID,
) -> Match | None:
    """
    Return an existing buyer/business Match.

    A unique buyer/business pair should be updated rather
    than duplicated during recalculation.
    """

    statement = (
        select(
            Match
        )
        .where(
            Match.buyer_id
            == buyer_id,

            Match.business_id
            == business_id,
        )
    )

    return session.scalar(
        statement
    )


# ============================================================
# MATCH PERSISTENCE
# ============================================================


def upsert_match(
    session: Session,
    evaluation: MatchEvaluation,
    *,
    matching_version: str = MATCHING_VERSION,
) -> Match:
    """
    Create or update one persisted Match.

    This method deliberately does NOT commit the transaction.
    Transaction ownership stays with the caller.
    """

    if not evaluation.eligible:
        raise MatchingRepositoryError(
            "Ineligible candidates must not "
            "be persisted as Match records."
        )

    if evaluation.score is None:
        raise MatchingRepositoryError(
            "Eligible MatchEvaluation must "
            "contain a score."
        )

    dimensions = (
        evaluation.dimensions
    )

    required_dimensions = {
        "industry",
        "geography",
        "purchase_price",
        "sde",
        "arr",
        "owner_involvement",
        "customer_concentration",
        "transition_training",
        "deal_preference",
    }

    missing_dimensions = (
        required_dimensions
        - set(
            dimensions.keys()
        )
    )

    if missing_dimensions:
        raise MatchingRepositoryError(
            "MatchEvaluation is missing "
            "dimensions: "
            + ", ".join(
                sorted(
                    missing_dimensions
                )
            )
        )

    match = get_existing_match(
        session,
        evaluation.buyer_id,
        evaluation.business_id,
    )

    if match is None:
        match = Match(
            buyer_id=(
                evaluation.buyer_id
            ),
            business_id=(
                evaluation.business_id
            ),
            score=_score_decimal(
                evaluation.score
            ),
            matching_version=(
                matching_version
            ),
            status=(
                MatchStatus.MATCHED
            ),
        )

        session.add(
            match
        )

    # --------------------------------------------------------
    # FINAL SCORE
    # --------------------------------------------------------

    match.score = _score_decimal(
        evaluation.score
    )

    # --------------------------------------------------------
    # DIMENSION SCORES
    # --------------------------------------------------------

    match.industry_score = _score_decimal(
        dimensions[
            "industry"
        ].score
    )

    match.geography_score = _score_decimal(
        dimensions[
            "geography"
        ].score
    )

    match.price_score = _score_decimal(
        dimensions[
            "purchase_price"
        ].score
    )

    match.sde_score = _score_decimal(
        dimensions[
            "sde"
        ].score
    )

    match.arr_score = _score_decimal(
        dimensions[
            "arr"
        ].score
    )

    match.owner_involvement_score = _score_decimal(
        dimensions[
            "owner_involvement"
        ].score
    )

    match.customer_concentration_score = _score_decimal(
        dimensions[
            "customer_concentration"
        ].score
    )

    match.transition_training_score = _score_decimal(
        dimensions[
            "transition_training"
        ].score
    )

    match.deal_preference_score = _score_decimal(
        dimensions[
            "deal_preference"
        ].score
    )

    # --------------------------------------------------------
    # WEIGHTED CONTRIBUTIONS
    # --------------------------------------------------------

    match.industry_contribution = _score_decimal(
        dimensions[
            "industry"
        ].contribution
    )

    match.geography_contribution = _score_decimal(
        dimensions[
            "geography"
        ].contribution
    )

    match.price_contribution = _score_decimal(
        dimensions[
            "purchase_price"
        ].contribution
    )

    match.sde_contribution = _score_decimal(
        dimensions[
            "sde"
        ].contribution
    )

    match.arr_contribution = _score_decimal(
        dimensions[
            "arr"
        ].contribution
    )

    match.owner_involvement_contribution = _score_decimal(
        dimensions[
            "owner_involvement"
        ].contribution
    )

    match.customer_concentration_contribution = _score_decimal(
        dimensions[
            "customer_concentration"
        ].contribution
    )

    match.transition_training_contribution = _score_decimal(
        dimensions[
            "transition_training"
        ].contribution
    )

    match.deal_preference_contribution = _score_decimal(
        dimensions[
            "deal_preference"
        ].contribution
    )

    # --------------------------------------------------------
    # VERSION + EXPLAINABILITY
    # --------------------------------------------------------

    match.score_breakdown = (
        build_score_breakdown(
            evaluation
        )
    )

    match.matching_version = (
        matching_version
    )

    session.flush()

    return match