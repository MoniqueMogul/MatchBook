from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id
from app.db.database import get_db
from app.matching.api_schema import (
    BuyerMatchesResponse,
    MatchDetailResponse,
    MatchDimensionResponse,
    MatchResponse, BusinessMatchSummary,
)
from app.matching.repository import MatchingRepository


router = APIRouter(
    prefix="/api/matches",
    tags=["Matching"],
)


# ============================================================
# BUYER RECOMMENDATION FEED
# ============================================================

@router.get(
    "",
    response_model=BuyerMatchesResponse,
)
def get_my_matches(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db),
) -> BuyerMatchesResponse:

    repository = MatchingRepository(session)

    # Supabase user ID -> BuyerProfile
    buyer = repository.get_buyer_profile_by_user_id(user_id)

    if buyer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Buyer profile not found",
        )

    # Fetch one extra record so we can determine whether
    # another page exists without running COUNT(*).
    rows = repository.list_recommendations_for_buyer(
        buyer_id=buyer.id,
        limit=limit,
        offset=offset,
    )

    has_more = len(rows) > limit

    matches = [
        MatchResponse.model_validate(match)
        for match in rows[:limit]
    ]

    return BuyerMatchesResponse(
        buyer_id=buyer.id,
        matches=matches,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


# ============================================================
# MATCH DETAIL
# ============================================================

@router.get(
    "/{match_id}",
    response_model=MatchDetailResponse,
)
def get_match_detail(
    match_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db),
) -> MatchDetailResponse:

    repository = MatchingRepository(session)

    # Resolve authenticated user to their BuyerProfile.
    buyer = repository.get_buyer_profile_by_user_id(user_id)

    if buyer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Buyer profile not found",
        )

    # buyer_id is part of this query so one buyer cannot
    # retrieve another buyer's match using its UUID.
    match = repository.get_recommendation_for_buyer(
        buyer_id=buyer.id,
        match_id=match_id,
    )

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    # score_breakdown was calculated by the matching engine
    # and persisted with the Match. Nothing is recalculated here.
    dimensions = [
        MatchDimensionResponse(
            dimension=dimension,
            alignment_score=data["score"],
            weight=data["weight"],
            contribution=data["contribution"],
        )
        for dimension, data in (match.score_breakdown or {}).items()
    ]

    return MatchDetailResponse(
        id=match.id,
        buyer_id=match.buyer_id,
        score=match.score,
        status=match.status,
        matching_version=match.matching_version,
        business=BusinessMatchSummary.model_validate(match.business),
        dimensions=dimensions,
        nda=match.nda,
        created_at=match.created_at,
        updated_at=match.updated_at,
    )