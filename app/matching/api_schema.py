from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.db_enum import MatchStatus


class MatchingAPIModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )


class BusinessMatchSummary(MatchingAPIModel):
    """
    Business information needed to render a match card.

    This deliberately contains only information appropriate
    for the recommendation feed.
    """

    id: UUID

    legal_name: str | None
    dba: str | None

    industry: str

    city: str
    state: str

    asking_price: Decimal | None
    sde: Decimal | None
    arr: Decimal | None

    years_in_operation: int | None

class MatchResponse(MatchingAPIModel):
    id: UUID

    score: Decimal
    status: MatchStatus

    business: BusinessMatchSummary

    created_at: datetime
    updated_at: datetime


class BuyerMatchesResponse(MatchingAPIModel):
    """
    One page of recommendations for a buyer.
    """

    buyer_id: UUID

    matches: list[MatchResponse]

    limit: int
    offset: int
    has_more: bool






class MatchDimensionResponse(MatchingAPIModel):
    """
    Deterministic explanation of one scoring dimension.
    """

    dimension: str

    alignment_score: float
    weight: float
    contribution: float


class MatchDetailResponse(MatchingAPIModel):
    """
    Detailed deterministic explanation for one Match.
    """

    id: UUID
    buyer_id: UUID

    score: Decimal
    status: MatchStatus
    matching_version: str

    business: BusinessMatchSummary

    dimensions: list[MatchDimensionResponse]

    created_at: datetime
    updated_at: datetime