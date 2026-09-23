from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.db_enum import (
    DealPreference,
    Industry,
    SubIndustry,
)
from app.intake.schemas.common import TargetLocation, TargetIndustryPreference


class MatchingModel(BaseModel):
    """
    Base model for internal Matching Engine data.

    Matching receives already validated application data.
    None means that a value or preference was not provided.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )


# ============================================================
# BUYER INPUT
# ============================================================


class BuyerMatchInput(MatchingModel):
    """
    Buyer preferences used by the Matching Engine.

    Optional preferences remain None.

    None means the buyer has not specified a constraint or
    preference for that dimension.
    """

    buyer_id: UUID

    # --------------------------------------------------------
    # Hard-filter dimensions
    # --------------------------------------------------------

    # Each industry contains the sub-industries the buyer
    # is willing to acquire.
    #
    # Example:
    # [
    #     {
    #         "industry": "automotive",
    #         "sub_industries": [
    #             "tire_shop",
    #             "auto_repair_and_maintenance"
    #         ]
    #     },
    #     {
    #         "industry": "technology",
    #         "sub_industries": [
    #             "saas"
    #         ]
    #     }
    # ]
    target_industry_preferences: (
        list[TargetIndustryPreference] | None
    ) = None

    target_locations: list[TargetLocation] | None = None

    maximum_purchase_price: Decimal | None = None

    # --------------------------------------------------------
    # FIT-scoring dimensions
    # --------------------------------------------------------

    minimum_sde: Decimal | None = None
    preferred_sde: Decimal | None = None

    minimum_arr: Decimal | None = None
    preferred_arr: Decimal | None = None

    preferred_owner_hours: int | None = None
    required_training_days: int | None = None

    deal_preference: DealPreference | None = None

    minimum_years_in_operation: int | None = None

    accepts_customer_concentration_above_25_percent: (
        bool | None
    ) = None


# ============================================================
# BUSINESS INPUT
# ============================================================


class BusinessMatchInput(MatchingModel):
    """
    Business data required by the Matching Engine.

    Optional business information remains None rather than
    being replaced with artificial defaults.
    """

    business_id: UUID

    # --------------------------------------------------------
    # Hard-filter dimensions
    # --------------------------------------------------------

    industry: Industry
    sub_industry: SubIndustry

    city: str
    county: str | None = None
    state: str

    asking_price: Decimal | None = None

    # --------------------------------------------------------
    # FIT-scoring dimensions
    # --------------------------------------------------------

    sde: Decimal | None = None
    arr: Decimal | None = None

    owner_hours: int | None = None
    transition_training_days: int | None = None

    deal_preference: DealPreference | None = None

    years_in_operation: int | None = None

    customer_concentration: Decimal | None = None


# ============================================================
# DIMENSION SCORE
# ============================================================


class DimensionScore(MatchingModel):
    """
    Score produced for one applicable matching dimension.

    score:
        Compatibility for the dimension from 0.0 to 1.0.

    weight:
        Effective weight after normalization.

    contribution:
        score * weight.
    """

    score: float
    weight: float
    contribution: float


# ============================================================
# MATCH EVALUATION
# ============================================================


class MatchEvaluation(MatchingModel):
    """
    Complete deterministic evaluation of one buyer/business pair.
    """

    buyer_id: UUID
    business_id: UUID

    score: float

    dimensions: dict[str, DimensionScore]


# ============================================================
# RANKED MATCH
# ============================================================


class RankedMatch(MatchingModel):
    """
    Match after threshold filtering and ranking.
    """

    rank: int
    evaluation: MatchEvaluation