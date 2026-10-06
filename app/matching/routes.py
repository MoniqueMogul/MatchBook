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
from app.matching.explanation import (MatchExplanationResponse, evidence_for, generate_for_buyer, ExplanationBusy)
from app.verification.business_images import business_image_url

import logging

logger = logging.getLogger(__name__)


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

    matches = []
    for match in rows[:limit]:
        response = MatchResponse.model_validate(match)
        response.business.profile_image_url = business_image_url(
            match.business.id, match.business.profile_image_key,
        )
        matches.append(response)

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

    business = BusinessMatchSummary.model_validate(match.business)
    business.profile_image_url = business_image_url(
        match.business.id, match.business.profile_image_key,
    )

    return MatchDetailResponse(
        id=match.id,
        buyer_id=match.buyer_id,
        score=match.score,
        status=match.status,
        matching_version=match.matching_version,
        business=business,
        dimensions=dimensions,
        created_at=match.created_at,
        updated_at=match.updated_at,
    )



@router.post(
    "/{match_id}/ai-explanation",
    response_model=MatchExplanationResponse,
)
def explain_match(
    match_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db),
) -> MatchExplanationResponse:
    repository = MatchingRepository(session)

    buyer = repository.get_buyer_profile_by_user_id(user_id)

    match = (
        repository.get_recommendation_for_buyer(
            buyer_id=buyer.id,
            match_id=match_id,
        )
        if buyer
        else None
    )

    if match is None:
        raise HTTPException(
            status_code=404,
            detail="Match not found",
        )

    evidence = evidence_for(match)

    if evidence is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This match does not have enough stored "
                "evidence to explain."
            ),
        )

    try:
        explanation = generate_for_buyer(
            evidence,
            user_id=user_id,
            match_id=match_id,
        )

        return MatchExplanationResponse(
            match_id=match_id,
            explanation=explanation,
        )

    except ExplanationBusy:
        raise HTTPException(
            status_code=429,
            detail=(
                "AI generation is busy or your limit has been "
                "reached. Please try again later."
            ),
        ) from None

    except Exception as exc:
        print(
            "AI EXPLANATION ERROR:",
            type(exc).__name__,
            repr(exc),
            flush=True,
        )

        logger.exception(
            "AI match explanation failed",
            extra={
                "match_id": str(match_id),
                "user_id": str(user_id),
            },
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "The AI explanation is temporarily unavailable. "
                "Please try again."
            ),
        ) from None