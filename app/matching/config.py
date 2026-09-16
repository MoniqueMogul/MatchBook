from typing import Final

from app.db.db_enum import MatchStatus



MATCHING_VERSION: Final[str] = "v1"

PRICE_TOLERANCE: Final[float] = 0.15

SCORING_WEIGHTS: Final[dict[str, float]] = {
    "industry": 0.00,
    "geography": 0.00,
    "purchase_price": 0.30,
    "sde": 0.30,
    "owner_involvement": 0.10,
    "transition_training": 0.10,
    "deal_preference": 0.10,
    "arr": 0.05,
    "customer_concentration": 0.05,
}

DEFAULT_MIN_FIT_THRESHOLD: Final[float] = 0.70
DEFAULT_TOP_N_MATCHES: Final[int] = 10


DEAL_COMPATIBILITY: Final[dict[tuple[str, str], float]] = {
    ("cash", "cash"): 1.00,
    ("cash", "financing"): 0.50,
    ("cash", "either"): 1.00,

    ("financing", "cash"): 0.50,
    ("financing", "financing"): 1.00,
    ("financing", "either"): 1.00,

    ("either", "cash"): 1.00,
    ("either", "financing"): 1.00,
    ("either", "either"): 1.00,
}


# Matching engine may replace these recommendations.
RERANKABLE_MATCH_STATUSES = {
    MatchStatus.MATCHED,
}


# These matches remain visible independently of Top-N ranking.
PROTECTED_MATCH_STATUSES = {
    MatchStatus.INTERESTED,
    MatchStatus.VERIFICATION,
    MatchStatus.NDA,
    MatchStatus.DUE_DILIGENCE,
    MatchStatus.OFFER,
    MatchStatus.LOI,
    MatchStatus.FINANCING,
    MatchStatus.CLOSING,
    MatchStatus.COMPLETED,
}


# These buyer/business pairs must not be matched again automatically.
BLOCKED_REMATCH_STATUSES = {
    MatchStatus.REJECTED,
}


def validate_scoring_weights() -> None:
    """
    Ensure all configured matching weights total 1.0.
    """
    total_weight = sum(SCORING_WEIGHTS.values())

    if abs(total_weight - 1.0) > 1e-9:
        raise ValueError(
            f"Matching weights must total 1.0. Current total: {total_weight}"
        )


validate_scoring_weights()