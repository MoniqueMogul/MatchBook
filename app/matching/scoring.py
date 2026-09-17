from decimal import Decimal

from app.db.db_enum import DealPreference
from app.matching.config import (
    DEAL_COMPATIBILITY,
    PRICE_TOLERANCE,
    SCORING_WEIGHTS,
)
from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
    DimensionScore,
    MatchEvaluation,
)


# ============================================================
# HELPERS
# ============================================================


def _clamp(value: float) -> float:
    """
    Force a score into the valid 0.0 -> 1.0 range.
    """

    return max(0.0, min(1.0, value))


def _score_minimum_preferred(
    *,
    actual: Decimal,
    minimum: Decimal | None,
    preferred: Decimal | None,
) -> float:
    """
    Score a value where higher is better.

    Used for SDE and ARR.

    Rules:
        actual < minimum:
            0.0

        actual >= preferred:
            1.0

        between minimum and preferred:
            linear score between 0.0 and 1.0

        only minimum exists:
            meeting minimum = 1.0

        only preferred exists:
            score proportionally toward preferred.
    """

    if minimum is not None and actual < minimum:
        return 0.0

    if preferred is not None:
        if actual >= preferred:
            return 1.0

        if minimum is not None:
            difference = preferred - minimum

            if difference <= 0:
                raise ValueError(
                    "preferred must be greater than minimum."
                )

            return _clamp(
                float(
                    (actual - minimum)
                    / difference
                )
            )

        if preferred <= 0:
            return 1.0

        return _clamp(
            float(actual / preferred)
        )

    if minimum is not None:
        return 1.0

    raise ValueError(
        "At least one preference must be supplied."
    )
# ============================================================
# PRICE
# ============================================================


def score_price(
        *,
        maximum_price: Decimal | None,
        asking_price: Decimal | None,
) -> float | None:
    """
    Score purchase-price compatibility.

    Price is only applicable when:
        - buyer specified a maximum price
        - business has an asking price

    At or below the buyer's maximum:
        1.0

    Between maximum and tolerance ceiling:
        score falls linearly from 1.0 -> 0.0

    Above tolerance:
        should already have been removed by the repository.
    """

    if (
            maximum_price is None
            or asking_price is None
    ):
        return None

    if asking_price <= maximum_price:
        return 1.0

    tolerance = Decimal(
        str(PRICE_TOLERANCE)
    )

    ceiling = (
            maximum_price
            * (Decimal("1") + tolerance)
    )

    if asking_price >= ceiling:
        return 0.0

    tolerance_range = ceiling - maximum_price

    if tolerance_range <= 0:
        return 0.0

    amount_over = (
            asking_price - maximum_price
    )

    return _clamp(
        1.0
        - float(
            amount_over / tolerance_range
        )
    )


# ============================================================
# SDE
# ============================================================


def score_sde(
        *,
        minimum_sde: Decimal | None,
        preferred_sde: Decimal | None,
        business_sde: Decimal | None,
) -> float | None:
    if (
            minimum_sde is None
            or preferred_sde is None
            or business_sde is None
    ):
        return None

    return _score_minimum_preferred(
        actual=business_sde,
        minimum=minimum_sde,
        preferred=preferred_sde,
    )


# ============================================================
# ARR
# ============================================================


def score_arr(
    *,
    minimum_arr: Decimal | None,
    preferred_arr: Decimal | None,
    business_arr: Decimal | None,
) -> float | None:

    if (
        minimum_arr is None
        or preferred_arr is None
        or business_arr is None
    ):
        return None

    return _score_minimum_preferred(
        actual=business_arr,
        minimum=minimum_arr,
        preferred=preferred_arr,
    )

# ============================================================
# OWNER INVOLVEMENT
# ============================================================


def score_owner_involvement(
        *,
        preferred_hours: int | None,
        actual_hours: int | None,
) -> float | None:
    """
    Lower owner involvement is better.

    At or below buyer preference:
        1.0

    Above preference:
        score falls proportionally.
    """

    if (
            preferred_hours is None
            or actual_hours is None
    ):
        return None

    if actual_hours <= preferred_hours:
        return 1.0

    if actual_hours == 0:
        return 1.0

    return _clamp(
        preferred_hours / actual_hours
    )


# ============================================================
# TRANSITION TRAINING
# ============================================================


def score_transition_training(
        *,
        required_days: int | None,
        available_days: int | None,
) -> float | None:
    """
    More available seller training is better.

    Available >= required:
        1.0

    Otherwise:
        proportional partial score.
    """

    if (
            required_days is None
            or available_days is None
    ):
        return None

    if required_days == 0:
        return 1.0

    if available_days >= required_days:
        return 1.0

    return _clamp(
        available_days / required_days
    )


# ============================================================
# DEAL PREFERENCE
# ============================================================


def score_deal_preference(
        *,
        buyer_preference: DealPreference | None,
        business_preference: DealPreference | None,
) -> float | None:
    """
    Score compatibility between the buyer's preferred deal
    structure and the seller's preferred deal structure.

    None means the dimension is not applicable.

    Compatibility values are defined centrally in
    DEAL_COMPATIBILITY.
    """

    if (
            buyer_preference is None
            or business_preference is None
    ):
        return None

    key = (
        buyer_preference.value,
        business_preference.value,
    )

    return DEAL_COMPATIBILITY[key]


# ============================================================
# CUSTOMER CONCENTRATION
# ============================================================


def score_customer_concentration(
        *,
        accepts_above_25_percent: bool | None,
        concentration: Decimal | None,
) -> float | None:
    """
    Score buyer tolerance for customer concentration.

    None:
        buyer did not specify a preference

    True:
        buyer accepts concentration above 25%

    False:
        buyer prefers concentration <= 25%
    """

    if (
            accepts_above_25_percent is None
            or concentration is None
    ):
        return None

    if accepts_above_25_percent:
        return 1.0

    if concentration <= Decimal("25"):
        return 1.0

    return 0.0


# ============================================================
# COMPLETE MATCH SCORE
# ============================================================


def score_candidate(
        *,
        buyer: BuyerMatchInput,
        business: BusinessMatchInput,
) -> MatchEvaluation:
    """
    Calculate deterministic FIT score for one buyer/business pair.

    Only applicable dimensions participate in the final score.

    Missing optional data does not automatically become a zero.
    """

    raw_scores: dict[str, float | None] = {
        "purchase_price": score_price(
            maximum_price=buyer.maximum_purchase_price,
            asking_price=business.asking_price,
        ),

        "sde": score_sde(
            minimum_sde=buyer.minimum_sde,
            preferred_sde=buyer.preferred_sde,
            business_sde=business.sde,
        ),

        "arr": score_arr(
            minimum_arr=buyer.minimum_arr,
            preferred_arr=buyer.preferred_arr,
            business_arr=business.arr,
        ),

        "owner_involvement": score_owner_involvement(
            preferred_hours=buyer.preferred_owner_hours,
            actual_hours=business.owner_hours,
        ),

        "transition_training": score_transition_training(
            required_days=buyer.required_training_days,
            available_days=business.transition_training_days,
        ),

        "deal_preference": score_deal_preference(
            buyer_preference=buyer.deal_preference,
            business_preference=business.deal_preference,
        ),

        "customer_concentration": score_customer_concentration(
            accepts_above_25_percent=(
                buyer.accepts_customer_concentration_above_25_percent
            ),
            concentration=business.customer_concentration,
        ),
    }

    applicable_scores = {
        name: score
        for name, score in raw_scores.items()
        if score is not None
    }

    if any(score is None for score in raw_scores.values()):
        return MatchEvaluation(
            buyer_id=buyer.buyer_id,
            business_id=business.business_id,
            score=0.0,
            dimensions={},
        )

    total_applicable_weight = sum(
        SCORING_WEIGHTS[name]
        for name in applicable_scores
    )

    dimensions: dict[str, DimensionScore] = {}

    final_score = 0.0

    for name, score in applicable_scores.items():
        original_weight = SCORING_WEIGHTS[name]

        normalized_weight = (
                original_weight
                / total_applicable_weight
        )

        contribution = (
                score * normalized_weight
        )

        dimensions[name] = DimensionScore(
            score=score,
            weight=normalized_weight,
            contribution=contribution,
        )

        final_score += contribution

    return MatchEvaluation(
        buyer_id=buyer.buyer_id,
        business_id=business.business_id,
        score=_clamp(final_score),
        dimensions=dimensions,
    )
