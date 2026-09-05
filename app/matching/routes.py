from dataclasses import asdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.matching.config import (
    DEFAULT_MIN_FIT_THRESHOLD,
    DEFAULT_TOP_N_MATCHES,
)

from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
)

from app.matching.service import (
    evaluate_candidate,
    rank_candidates,
)


router = APIRouter(
    prefix="/api/matches",
    tags=["Matching"],
)


# ============================================================
# API REQUEST MODELS
# ============================================================


class BuyerMatchRequest(BaseModel):
    """
    Buyer matching preferences supplied through the API.
    """

    buyer_id: int

    target_industries: list[str] | None = None

    target_locations: dict[str, Any] | None = None

    maximum_purchase_price: Decimal | None = None

    minimum_sde: Decimal | None = None

    preferred_sde: Decimal

    preferred_owner_hours: float = Field(
        ge=0,
    )

    required_training_days: float = Field(
        ge=0,
    )

    deal_preference: str

    minimum_arr: Decimal = Field(
        ge=0,
    )

    preferred_arr: Decimal = Field(
        ge=0,
    )

    accepts_customer_concentration_above_25_percent: bool

    minimum_years_in_operation: int | None = Field(
        default=None,
        ge=0,
    )


class BusinessMatchRequest(BaseModel):
    """
    Seller/business data supplied to the Matching Engine.
    """

    business_id: int

    industry: str | None = None

    city: str | None = None
    county: str | None = None
    state: str | None = None

    asking_price: Decimal | None = Field(
        default=None,
        ge=0,
    )

    sde: Decimal | None = Field(
        default=None,
        ge=0,
    )

    owner_hours: float = Field(
        ge=0,
    )

    transition_training_days: float = Field(
        ge=0,
    )

    deal_preference: str

    arr: Decimal = Field(
        ge=0,
    )

    largest_customer_percent: float = Field(
        ge=0,
        le=100,
    )

    years_in_operation: int | None = Field(
        default=None,
        ge=0,
    )


class EvaluateMatchRequest(BaseModel):
    buyer: BuyerMatchRequest
    business: BusinessMatchRequest


class RankMatchesRequest(BaseModel):
    buyer: BuyerMatchRequest

    businesses: list[
        BusinessMatchRequest
    ]


# ============================================================
# INPUT CONVERSION
# ============================================================


def _build_buyer(
    request: BuyerMatchRequest,
) -> BuyerMatchInput:
    """
    Convert the API request model into the pure Matching Engine
    input dataclass.
    """

    if (
        request.preferred_sde
        < (
            request.minimum_sde
            or Decimal("0")
        )
    ):
        raise ValueError(
            "preferred_sde cannot be below minimum_sde"
        )

    if (
        request.preferred_arr
        < request.minimum_arr
    ):
        raise ValueError(
            "preferred_arr cannot be below minimum_arr"
        )

    return BuyerMatchInput(
        buyer_id=request.buyer_id,

        target_industries=(
            request.target_industries
        ),

        target_locations=(
            request.target_locations
        ),

        maximum_purchase_price=(
            request.maximum_purchase_price
        ),

        minimum_sde=(
            request.minimum_sde
        ),

        preferred_sde=(
            request.preferred_sde
        ),

        preferred_owner_hours=(
            request.preferred_owner_hours
        ),

        required_training_days=(
            request.required_training_days
        ),

        deal_preference=(
            request.deal_preference
        ),

        minimum_arr=(
            request.minimum_arr
        ),

        preferred_arr=(
            request.preferred_arr
        ),

        accepts_customer_concentration_above_25_percent=(
            request.accepts_customer_concentration_above_25_percent
        ),

        minimum_years_in_operation=(
            request.minimum_years_in_operation
        ),
    )


def _build_business(
    request: BusinessMatchRequest,
) -> BusinessMatchInput:
    """
    Convert API business data into the pure Matching Engine input.
    """

    return BusinessMatchInput(
        business_id=(
            request.business_id
        ),

        industry=(
            request.industry
        ),

        city=(
            request.city
        ),

        county=(
            request.county
        ),

        state=(
            request.state
        ),

        asking_price=(
            request.asking_price
        ),

        sde=(
            request.sde
        ),

        owner_hours=(
            request.owner_hours
        ),

        transition_training_days=(
            request.transition_training_days
        ),

        deal_preference=(
            request.deal_preference
        ),

        arr=(
            request.arr
        ),

        largest_customer_percent=(
            request.largest_customer_percent
        ),

        years_in_operation=(
            request.years_in_operation
        ),
    )


# ============================================================
# HEALTH / METADATA
# ============================================================


@router.get(
    "/health",
)
def matching_health() -> dict[str, str]:
    """
    Lightweight Matching Engine health endpoint.
    """

    return {
        "status": "healthy",
        "service": "matching",
    }


# ============================================================
# SINGLE CANDIDATE EVALUATION
# ============================================================


@router.post(
    "/evaluate",
)
def evaluate_match(
    request: EvaluateMatchRequest,
    minimum_threshold: float = Query(
        default=DEFAULT_MIN_FIT_THRESHOLD,
        ge=0.0,
        le=1.0,
    ),
) -> dict[str, Any]:
    """
    Evaluate one buyer/business pair.

    Hard eligibility is applied before deterministic scoring.
    """

    try:
        buyer = _build_buyer(
            request.buyer
        )

        business = _build_business(
            request.business
        )

        result = evaluate_candidate(
            buyer,
            business,
            minimum_threshold=(
                minimum_threshold
            ),
        )

        return asdict(
            result
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(
                exc
            ),
        ) from exc


# ============================================================
# RANK MULTIPLE BUSINESSES
# ============================================================


@router.post(
    "/rank",
)
def rank_matches(
    request: RankMatchesRequest,
    minimum_threshold: float = Query(
        default=DEFAULT_MIN_FIT_THRESHOLD,
        ge=0.0,
        le=1.0,
    ),
    top_n: int = Query(
        default=DEFAULT_TOP_N_MATCHES,
        ge=1,
        le=100,
    ),
) -> dict[str, Any]:
    """
    Evaluate and rank candidate businesses for one buyer.

    Only candidates that:
        - pass hard eligibility
        - meet the configured FIT threshold

    are returned.
    """

    try:
        buyer = _build_buyer(
            request.buyer
        )

        businesses = [
            _build_business(
                business
            )
            for business
            in request.businesses
        ]

        ranked = rank_candidates(
            buyer,
            businesses,
            minimum_threshold=(
                minimum_threshold
            ),
            top_n=(
                top_n
            ),
        )

        return {
            "buyer_id": (
                buyer.buyer_id
            ),
            "count": len(
                ranked
            ),
            "matches": [
                asdict(
                    result
                )
                for result
                in ranked
            ],
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(
                exc
            ),
        ) from exc