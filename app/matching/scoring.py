from dataclasses import dataclass
from decimal import Decimal

from app.matching.config import (
    DEAL_COMPATIBILITY,
    PRICE_TOLERANCE,
    SCORING_WEIGHTS,
)


@dataclass(frozen=True)
class MatchScoreResult:
    """
    Complete deterministic V1 scoring result.
    """

    industry_score: float
    geography_score: float
    price_score: float
    sde_score: float
    owner_involvement_score: float
    training_score: float
    deal_score: float
    arr_score: float
    customer_concentration_score: float

    industry_contribution: float
    geography_contribution: float
    price_contribution: float
    sde_contribution: float
    owner_involvement_contribution: float
    training_contribution: float
    deal_contribution: float
    arr_contribution: float
    customer_concentration_contribution: float

    match_score: float
    match_percentage: float


def _clamp_score(value: float) -> float:
    """
    Keep a compatibility score between 0.0 and 1.0.
    """
    return max(0.0, min(1.0, value))


# ============================================================
# INDUSTRY
# ============================================================


def calculate_industry_score(
    industry_matches: bool,
) -> float:
    """
    V1 Industry score.

    Industry is primarily a hard-filter dimension in V1.

    Match:
        1.00

    No match:
        0.00

    V1 scoring weight is currently 0%.
    """
    return 1.0 if industry_matches else 0.0


# ============================================================
# GEOGRAPHY
# ============================================================


def calculate_geography_score(
    geography_matches: bool,
) -> float:
    """
    V1 Geography score.

    Geography is deterministic in V1.

    Match:
        1.00

    No match:
        0.00

    V1 scoring weight is currently 0%.
    """
    return 1.0 if geography_matches else 0.0


# ============================================================
# PURCHASE PRICE
# ============================================================


def calculate_price_score(
    maximum_purchase_price: Decimal,
    seller_price: Decimal,
    price_tolerance: float = PRICE_TOLERANCE,
) -> float:
    """
    Calculate V1 purchase-price compatibility.

    If:
        Seller Price <= Buyer Maximum Price
    then:
        Price Score = 1.00

    If:
        Buyer Maximum Price < Seller Price <= Absolute Ceiling
    then:
        Price Score =
            1 - (
                (Seller Price - Maximum Price)
                /
                (Maximum Price * Price Tolerance)
            )

    Seller prices above the absolute ceiling should already have
    been rejected by the eligibility layer. If one reaches this
    function anyway, its compatibility score is 0.00.
    """
    if maximum_purchase_price <= 0:
        raise ValueError(
            "maximum_purchase_price must be greater than zero"
        )

    if seller_price < 0:
        raise ValueError(
            "seller_price cannot be negative"
        )

    tolerance = Decimal(str(price_tolerance))

    if tolerance <= 0:
        raise ValueError(
            "price_tolerance must be greater than zero"
        )

    if seller_price <= maximum_purchase_price:
        return 1.0

    tolerance_amount = (
        maximum_purchase_price * tolerance
    )

    absolute_ceiling = (
        maximum_purchase_price + tolerance_amount
    )

    if seller_price > absolute_ceiling:
        return 0.0

    score = Decimal("1") - (
        (seller_price - maximum_purchase_price)
        / tolerance_amount
    )

    return _clamp_score(float(score))


# ============================================================
# SDE
# ============================================================


def calculate_sde_score(
    minimum_sde: Decimal,
    preferred_sde: Decimal,
    seller_sde: Decimal,
) -> float:
    """
    Calculate V1 SDE compatibility.

    Seller SDE >= Preferred SDE:
        1.00

    Minimum SDE <= Seller SDE < Preferred SDE:
        (Seller SDE - Minimum SDE)
        /
        (Preferred SDE - Minimum SDE)

    Seller SDE below Minimum SDE should already have been rejected
    by eligibility. If supplied here, score is 0.00.
    """
    if minimum_sde < 0:
        raise ValueError(
            "minimum_sde cannot be negative"
        )

    if preferred_sde < minimum_sde:
        raise ValueError(
            "preferred_sde cannot be below minimum_sde"
        )

    if seller_sde < minimum_sde:
        return 0.0

    if seller_sde >= preferred_sde:
        return 1.0

    # If minimum and preferred are equal, the earlier conditions
    # fully determine the result.
    if preferred_sde == minimum_sde:
        return 1.0

    score = (
        (seller_sde - minimum_sde)
        /
        (preferred_sde - minimum_sde)
    )

    return _clamp_score(float(score))


# ============================================================
# OWNER INVOLVEMENT
# ============================================================


def calculate_owner_involvement_score(
    buyer_preferred_hours: float,
    seller_owner_hours: float,
) -> float:
    """
    Calculate V1 owner-involvement compatibility.

    Seller Hours <= Buyer Preferred Hours:
        1.00

    Seller Hours > Buyer Preferred Hours:
        1 - (
            (Seller Hours - Buyer Preferred Hours)
            /
            Buyer Preferred Hours
        )

    Result is capped between 0.00 and 1.00.
    """
    if buyer_preferred_hours < 0:
        raise ValueError(
            "buyer_preferred_hours cannot be negative"
        )

    if seller_owner_hours < 0:
        raise ValueError(
            "seller_owner_hours cannot be negative"
        )

    if seller_owner_hours <= buyer_preferred_hours:
        return 1.0

    # The document's formula uses buyer preferred hours as the
    # denominator. When preference is zero, any positive seller
    # requirement is incompatible.
    if buyer_preferred_hours == 0:
        return 0.0

    score = 1.0 - (
        (
            seller_owner_hours
            - buyer_preferred_hours
        )
        / buyer_preferred_hours
    )

    return _clamp_score(score)


# ============================================================
# TRANSITION TRAINING
# ============================================================


def calculate_training_score(
    buyer_required_training_days: float,
    seller_offered_training_days: float,
) -> float:
    """
    Calculate V1 transition-training compatibility.

    Seller Training >= Buyer Required Training:
        1.00

    0 < Seller Training < Buyer Required Training:
        Seller Training / Buyer Required Training

    Seller Training == 0:
        0.00
    """
    if buyer_required_training_days < 0:
        raise ValueError(
            "buyer_required_training_days cannot be negative"
        )

    if seller_offered_training_days < 0:
        raise ValueError(
            "seller_offered_training_days cannot be negative"
        )

    # If the buyer requires no training, the requirement is
    # automatically satisfied.
    if buyer_required_training_days == 0:
        return 1.0

    if seller_offered_training_days >= (
        buyer_required_training_days
    ):
        return 1.0

    if seller_offered_training_days == 0:
        return 0.0

    score = (
        seller_offered_training_days
        /
        buyer_required_training_days
    )

    return _clamp_score(score)


# ============================================================
# DEAL PREFERENCE
# ============================================================


def calculate_deal_score(
    buyer_preference: str,
    seller_preference: str,
) -> float:
    """
    Calculate V1 categorical deal compatibility using the
    configured compatibility table.
    """
    buyer = buyer_preference.strip().lower()
    seller = seller_preference.strip().lower()

    key = (buyer, seller)

    if key not in DEAL_COMPATIBILITY:
        raise ValueError(
            "Unsupported deal preference combination: "
            f"{buyer_preference!r}, "
            f"{seller_preference!r}"
        )

    return DEAL_COMPATIBILITY[key]


# ============================================================
# ARR / RECURRING REVENUE
# ============================================================


def calculate_arr_score(
    minimum_arr: Decimal,
    preferred_arr: Decimal,
    seller_arr: Decimal,
) -> float:
    """
    Calculate V1 ARR / recurring-revenue compatibility.

    Seller ARR >= Preferred ARR:
        1.00

    Minimum ARR <= Seller ARR < Preferred ARR:
        (Seller ARR - Minimum ARR)
        /
        (Preferred ARR - Minimum ARR)

    Seller ARR < Minimum ARR:
        0.00

    ARR is a soft scoring dimension in V1.
    """
    if minimum_arr < 0:
        raise ValueError(
            "minimum_arr cannot be negative"
        )

    if preferred_arr < minimum_arr:
        raise ValueError(
            "preferred_arr cannot be below minimum_arr"
        )

    if seller_arr < minimum_arr:
        return 0.0

    if seller_arr >= preferred_arr:
        return 1.0

    if preferred_arr == minimum_arr:
        return 1.0

    score = (
        (seller_arr - minimum_arr)
        /
        (preferred_arr - minimum_arr)
    )

    return _clamp_score(float(score))


# ============================================================
# CUSTOMER CONCENTRATION
# ============================================================


def calculate_customer_concentration_score(
    buyer_accepts_above_25_percent: bool,
    seller_largest_customer_percent: float,
) -> float:
    """
    Calculate V1 customer-concentration compatibility.

    Buyer accepts concentration above 25%:
        1.00 regardless of seller concentration.

    Buyer does not accept >25% AND seller <=25%:
        1.00

    Buyer does not accept >25% AND seller >25%:
        0.50
    """
    if (
        seller_largest_customer_percent < 0
        or seller_largest_customer_percent > 100
    ):
        raise ValueError(
            "seller_largest_customer_percent "
            "must be between 0 and 100"
        )

    if buyer_accepts_above_25_percent:
        return 1.0

    if seller_largest_customer_percent <= 25:
        return 1.0

    return 0.5


# ============================================================
# FINAL WEIGHTED MATCH SCORE
# ============================================================


def calculate_match_score(
    *,
    industry_score: float,
    geography_score: float,
    price_score: float,
    sde_score: float,
    owner_involvement_score: float,
    training_score: float,
    deal_score: float,
    arr_score: float,
    customer_concentration_score: float,
) -> MatchScoreResult:
    """
    Apply V1 configured weights and return the complete,
    explainable deterministic match result.
    """

    scores = {
        "industry": _clamp_score(industry_score),
        "geography": _clamp_score(geography_score),
        "purchase_price": _clamp_score(price_score),
        "sde": _clamp_score(sde_score),
        "owner_involvement": _clamp_score(
            owner_involvement_score
        ),
        "transition_training": _clamp_score(
            training_score
        ),
        "deal_preference": _clamp_score(
            deal_score
        ),
        "arr": _clamp_score(arr_score),
        "customer_concentration": _clamp_score(
            customer_concentration_score
        ),
    }

    contributions = {
        dimension: (
            score * SCORING_WEIGHTS[dimension]
        )
        for dimension, score in scores.items()
    }

    match_score = sum(
        contributions.values()
    )

    # Prevent floating-point artifacts such as
    # 0.8549999999999999.
    match_score = round(match_score, 10)
    match_percentage = round(
        match_score * 100,
        2,
    )

    return MatchScoreResult(
        industry_score=scores["industry"],
        geography_score=scores["geography"],
        price_score=scores["purchase_price"],
        sde_score=scores["sde"],
        owner_involvement_score=scores[
            "owner_involvement"
        ],
        training_score=scores[
            "transition_training"
        ],
        deal_score=scores["deal_preference"],
        arr_score=scores["arr"],
        customer_concentration_score=scores[
            "customer_concentration"
        ],

        industry_contribution=contributions[
            "industry"
        ],
        geography_contribution=contributions[
            "geography"
        ],
        price_contribution=contributions[
            "purchase_price"
        ],
        sde_contribution=contributions[
            "sde"
        ],
        owner_involvement_contribution=contributions[
            "owner_involvement"
        ],
        training_contribution=contributions[
            "transition_training"
        ],
        deal_contribution=contributions[
            "deal_preference"
        ],
        arr_contribution=contributions[
            "arr"
        ],
        customer_concentration_contribution=(
            contributions[
                "customer_concentration"
            ]
        ),

        match_score=match_score,
        match_percentage=match_percentage,
    )