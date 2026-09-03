from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class BuyerMatchInput:
    """
    Structured buyer data required by the V1 Matching Engine.
    """

    buyer_id: int

    target_industries: list[str] | None
    target_locations: dict[str, Any] | None

    maximum_purchase_price: Decimal | None

    minimum_sde: Decimal | None
    preferred_sde: Decimal

    preferred_owner_hours: float

    required_training_days: float

    deal_preference: str

    minimum_arr: Decimal
    preferred_arr: Decimal

    accepts_customer_concentration_above_25_percent: bool


@dataclass(frozen=True)
class BusinessMatchInput:
    """
    Structured business/seller data required by the V1 Matching Engine.
    """

    business_id: int

    industry: str | None

    city: str | None
    county: str | None
    state: str | None

    asking_price: Decimal | None

    sde: Decimal | None

    owner_hours: float

    transition_training_days: float

    deal_preference: str

    arr: Decimal

    largest_customer_percent: float


@dataclass(frozen=True)
class DimensionScore:
    """
    Explainable score for one matching dimension.
    """

    score: float
    weight: float
    contribution: float


@dataclass(frozen=True)
class MatchEvaluation:
    """
    Complete evaluation of one buyer/business pair.
    """

    buyer_id: int
    business_id: int

    eligible: bool
    failed_constraints: list[str]

    score: float | None
    percentage: float | None

    dimensions: dict[str, DimensionScore]

    meets_threshold: bool


@dataclass(frozen=True)
class RankedMatch:
    """
    Ranked eligible candidate.
    """

    rank: int
    evaluation: MatchEvaluation