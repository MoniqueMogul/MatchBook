from app.matching.config import (
    DEFAULT_MIN_FIT_THRESHOLD,
    DEFAULT_TOP_N_MATCHES,
    SCORING_WEIGHTS,
)

from app.matching.eligibility import (
    check_geography_eligibility,
    check_industry_eligibility,
    evaluate_eligibility,
)

from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
    DimensionScore,
    MatchEvaluation,
    RankedMatch,
)

from app.matching.scoring import (
    calculate_arr_score,
    calculate_customer_concentration_score,
    calculate_deal_score,
    calculate_geography_score,
    calculate_industry_score,
    calculate_match_score,
    calculate_owner_involvement_score,
    calculate_price_score,
    calculate_sde_score,
    calculate_training_score,
)


def evaluate_candidate(
    buyer: BuyerMatchInput,
    business: BusinessMatchInput,
    *,
    minimum_threshold: float = DEFAULT_MIN_FIT_THRESHOLD,
) -> MatchEvaluation:
    """
    Evaluate one business against one buyer.

    V1 workflow:

        Eligibility
            ↓
        Dimension scoring
            ↓
        Weighted FIT score
            ↓
        Threshold evaluation
    """

    eligibility = evaluate_eligibility(
        target_industries=buyer.target_industries,
        target_locations=buyer.target_locations,
        maximum_purchase_price=buyer.maximum_purchase_price,
        minimum_sde=buyer.minimum_sde,
        business_industry=business.industry,
        business_city=business.city,
        business_county=business.county,
        business_state=business.state,
        asking_price=business.asking_price,
        seller_sde=business.sde,
    )

    if not eligibility.eligible:
        return MatchEvaluation(
            buyer_id=buyer.buyer_id,
            business_id=business.business_id,
            eligible=False,
            failed_constraints=eligibility.failed_constraints,
            score=None,
            percentage=None,
            dimensions={},
            meets_threshold=False,
        )

    # --------------------------------------------------------
    # Industry
    # --------------------------------------------------------

    industry_matches = check_industry_eligibility(
        buyer.target_industries,
        business.industry,
    )

    industry_score = calculate_industry_score(
        industry_matches
    )

    # --------------------------------------------------------
    # Geography
    # --------------------------------------------------------

    geography_matches = check_geography_eligibility(
        buyer.target_locations,
        business_city=business.city,
        business_county=business.county,
        business_state=business.state,
    )

    geography_score = calculate_geography_score(
        geography_matches
    )

    # --------------------------------------------------------
    # Purchase Price
    # --------------------------------------------------------

    if (
        buyer.maximum_purchase_price is None
        or business.asking_price is None
    ):
        price_score = 1.0
    else:
        price_score = calculate_price_score(
            maximum_purchase_price=buyer.maximum_purchase_price,
            seller_price=business.asking_price,
        )

    # --------------------------------------------------------
    # SDE
    # --------------------------------------------------------

    if business.sde is None:
        sde_score = 0.0
    else:
        minimum_sde = (
            buyer.minimum_sde
            if buyer.minimum_sde is not None
            else business.sde
        )

        preferred_sde = max(
            buyer.preferred_sde,
            minimum_sde,
        )

        sde_score = calculate_sde_score(
            minimum_sde=minimum_sde,
            preferred_sde=preferred_sde,
            seller_sde=business.sde,
        )

    # --------------------------------------------------------
    # Owner Involvement
    # --------------------------------------------------------

    owner_score = calculate_owner_involvement_score(
        buyer_preferred_hours=buyer.preferred_owner_hours,
        seller_owner_hours=business.owner_hours,
    )

    # --------------------------------------------------------
    # Transition Training
    # --------------------------------------------------------

    training_score = calculate_training_score(
        buyer_required_training_days=buyer.required_training_days,
        seller_offered_training_days=(
            business.transition_training_days
        ),
    )

    # --------------------------------------------------------
    # Deal Preference
    # --------------------------------------------------------

    deal_score = calculate_deal_score(
        buyer.deal_preference,
        business.deal_preference,
    )

    # --------------------------------------------------------
    # ARR
    # --------------------------------------------------------

    arr_score = calculate_arr_score(
        minimum_arr=buyer.minimum_arr,
        preferred_arr=buyer.preferred_arr,
        seller_arr=business.arr,
    )

    # --------------------------------------------------------
    # Customer Concentration
    # --------------------------------------------------------

    customer_concentration_score = (
        calculate_customer_concentration_score(
            buyer.accepts_customer_concentration_above_25_percent,
            business.largest_customer_percent,
        )
    )

    # --------------------------------------------------------
    # Final Weighted Score
    # --------------------------------------------------------

    final_result = calculate_match_score(
        industry_score=industry_score,
        geography_score=geography_score,
        price_score=price_score,
        sde_score=sde_score,
        owner_involvement_score=owner_score,
        training_score=training_score,
        deal_score=deal_score,
        arr_score=arr_score,
        customer_concentration_score=(
            customer_concentration_score
        ),
    )

    raw_scores = {
        "industry": final_result.industry_score,
        "geography": final_result.geography_score,
        "purchase_price": final_result.price_score,
        "sde": final_result.sde_score,
        "owner_involvement": (
            final_result.owner_involvement_score
        ),
        "transition_training": (
            final_result.training_score
        ),
        "deal_preference": final_result.deal_score,
        "arr": final_result.arr_score,
        "customer_concentration": (
            final_result.customer_concentration_score
        ),
    }

    dimensions: dict[str, DimensionScore] = {}

    for dimension, score in raw_scores.items():
        weight = SCORING_WEIGHTS[dimension]

        dimensions[dimension] = DimensionScore(
            score=score,
            weight=weight,
            contribution=score * weight,
        )

    return MatchEvaluation(
        buyer_id=buyer.buyer_id,
        business_id=business.business_id,
        eligible=True,
        failed_constraints=[],
        score=final_result.match_score,
        percentage=final_result.match_percentage,
        dimensions=dimensions,
        meets_threshold=(
            final_result.match_score
            >= minimum_threshold
        ),
    )


def rank_candidates(
    buyer: BuyerMatchInput,
    businesses: list[BusinessMatchInput],
    *,
    minimum_threshold: float = DEFAULT_MIN_FIT_THRESHOLD,
    top_n: int = DEFAULT_TOP_N_MATCHES,
) -> list[RankedMatch]:
    """
    Evaluate, filter, sort, and rank candidate businesses.

    Only candidates that:
        1. pass eligibility, and
        2. meet the configured FIT threshold

    are returned.
    """

    if top_n <= 0:
        return []

    evaluations = [
        evaluate_candidate(
            buyer,
            business,
            minimum_threshold=minimum_threshold,
        )
        for business in businesses
    ]

    qualifying = [
        evaluation
        for evaluation in evaluations
        if (
            evaluation.eligible
            and evaluation.meets_threshold
            and evaluation.score is not None
        )
    ]

    qualifying.sort(
        key=lambda evaluation: (
            evaluation.score
            if evaluation.score is not None
            else 0.0
        ),
        reverse=True,
    )

    qualifying = qualifying[:top_n]

    return [
        RankedMatch(
            rank=index,
            evaluation=evaluation,
        )
        for index, evaluation in enumerate(
            qualifying,
            start=1,
        )
    ]