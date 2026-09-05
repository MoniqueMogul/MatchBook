from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.matching.config import (
    DEFAULT_MIN_FIT_THRESHOLD,
    DEFAULT_TOP_N_MATCHES,
)

from app.matching.repository import (
    MatchingDataIncompleteError,
    build_business_match_input,
    build_buyer_match_input,
    get_buyer_preferences,
    get_candidate_businesses,
    upsert_match,
)

from app.matching.schemas import (
    BusinessMatchInput,
    RankedMatch,
)

from app.matching.service import (
    rank_candidates,
)


logger = logging.getLogger(
    __name__
)


class MatchingDatabaseServiceError(Exception):
    """
    Raised when database-backed Matching Engine
    orchestration fails.
    """


def _build_candidate_inputs(
    businesses,
) -> list[BusinessMatchInput]:
    """
    Convert SQLAlchemy Business records into pure
    Matching Engine inputs.

    A single incomplete business should not prevent
    every other valid candidate from being evaluated.

    Incomplete businesses are skipped and logged.
    """

    candidate_inputs: list[
        BusinessMatchInput
    ] = []

    for business in businesses:
        try:
            candidate = (
                build_business_match_input(
                    business
                )
            )

            candidate_inputs.append(
                candidate
            )

        except MatchingDataIncompleteError:
            logger.warning(
                (
                    "Skipping business_id=%s "
                    "because required V1 matching "
                    "data is incomplete."
                ),
                getattr(
                    business,
                    "id",
                    None,
                ),
                exc_info=True,
            )

    return candidate_inputs


def recalculate_matches_for_buyer(
    session: Session,
    buyer_id: UUID,
    *,
    minimum_threshold: float = (
        DEFAULT_MIN_FIT_THRESHOLD
    ),
    top_n: int = (
        DEFAULT_TOP_N_MATCHES
    ),
) -> list[RankedMatch]:
    """
    Run the database-backed V1 Matching Engine
    for one buyer.

    Workflow:

        buyer_id
            ↓
        BuyerPreferences
            ↓
        Candidate Businesses
            ↓
        Database model -> Matching input mapping
            ↓
        Hard eligibility filters
            ↓
        Deterministic FIT scoring
            ↓
        Threshold filtering
            ↓
        Top-N ranking
            ↓
        Persist Match records
            ↓
        Commit transaction

    PostgreSQL remains the system of record.

    Redis is intentionally not required here.
    Cache integration remains outside the core
    database transaction.
    """

    if not (
        0.0
        <= minimum_threshold
        <= 1.0
    ):
        raise ValueError(
            (
                "minimum_threshold must "
                "be between 0.0 and 1.0"
            )
        )

    if top_n <= 0:
        raise ValueError(
            "top_n must be greater than 0"
        )

    try:
        # ====================================================
        # LOAD BUYER PREFERENCES
        # ====================================================

        preferences = (
            get_buyer_preferences(
                session,
                buyer_id,
            )
        )

        buyer_input = (
            build_buyer_match_input(
                preferences
            )
        )

        # ====================================================
        # LOAD CANDIDATE BUSINESSES
        # ====================================================

        businesses = (
            get_candidate_businesses(
                session,
                preferences,
            )
        )

        if not businesses:
            return []

        # ====================================================
        # DATABASE -> MATCHING INPUT
        # ====================================================

        candidate_inputs = (
            _build_candidate_inputs(
                businesses
            )
        )

        if not candidate_inputs:
            return []

        # ====================================================
        # MATCH + RANK
        # ====================================================

        ranked_matches = (
            rank_candidates(
                buyer_input,
                candidate_inputs,
                minimum_threshold=(
                    minimum_threshold
                ),
                top_n=(
                    top_n
                ),
            )
        )

        # ====================================================
        # PERSIST MATCH RESULTS
        # ====================================================

        for ranked_match in ranked_matches:
            upsert_match(
                session,
                ranked_match.evaluation,
            )

        # Transaction belongs to this orchestration layer.
        session.commit()

        return ranked_matches

    except Exception as exc:
        session.rollback()

        logger.exception(
            (
                "Database-backed matching failed "
                "for buyer_id=%s"
            ),
            buyer_id,
        )

        # Preserve known validation/domain exceptions so
        # FastAPI can map them appropriately later.
        if isinstance(
            exc,
            (
                ValueError,
                MatchingDataIncompleteError,
            ),
        ):
            raise

        raise MatchingDatabaseServiceError(
            (
                "Unable to recalculate matches "
                f"for buyer_id={buyer_id}"
            )
        ) from exc