import logging
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from redis.exceptions import RedisError

from app.celery_app import celery_app

from app.matching.cache import (
    get_match_cache,
)

from app.matching.config import (
    DEFAULT_MIN_FIT_THRESHOLD,
    DEFAULT_TOP_N_MATCHES,
)

from app.matching.schemas import (
    BusinessMatchInput,
    BuyerMatchInput,
)

from app.matching.service import (
    rank_candidates,
)


logger = logging.getLogger(
    __name__
)


def _to_decimal(
    value: Any,
) -> Decimal:
    """
    Safely convert serialized numbers into Decimal.
    """
    return Decimal(
        str(
            value
        )
    )


# ============================================================
# TASK PAYLOAD BUILDERS
# ============================================================


def _build_buyer_input(
    payload: dict[str, Any],
) -> BuyerMatchInput:
    """
    Convert JSON-safe task data into BuyerMatchInput.
    """

    return BuyerMatchInput(
        buyer_id=int(
            payload[
                "buyer_id"
            ]
        ),

        target_industries=(
            payload.get(
                "target_industries"
            )
        ),

        target_locations=(
            payload.get(
                "target_locations"
            )
        ),

        maximum_purchase_price=(
            _to_decimal(
                payload[
                    "maximum_purchase_price"
                ]
            )
            if payload.get(
                "maximum_purchase_price"
            )
            is not None
            else None
        ),

        minimum_sde=(
            _to_decimal(
                payload[
                    "minimum_sde"
                ]
            )
            if payload.get(
                "minimum_sde"
            )
            is not None
            else None
        ),

        preferred_sde=_to_decimal(
            payload[
                "preferred_sde"
            ]
        ),

        preferred_owner_hours=float(
            payload[
                "preferred_owner_hours"
            ]
        ),

        required_training_days=float(
            payload[
                "required_training_days"
            ]
        ),

        deal_preference=str(
            payload[
                "deal_preference"
            ]
        ),

        minimum_arr=_to_decimal(
            payload[
                "minimum_arr"
            ]
        ),

        preferred_arr=_to_decimal(
            payload[
                "preferred_arr"
            ]
        ),

        accepts_customer_concentration_above_25_percent=bool(
            payload[
                "accepts_customer_concentration_above_25_percent"
            ]
        ),

        minimum_years_in_operation=(
            int(
                payload[
                    "minimum_years_in_operation"
                ]
            )
            if payload.get(
                "minimum_years_in_operation"
            )
            is not None
            else None
        ),
    )


def _build_business_input(
    payload: dict[str, Any],
) -> BusinessMatchInput:
    """
    Convert JSON-safe task data into BusinessMatchInput.
    """

    return BusinessMatchInput(
        business_id=int(
            payload[
                "business_id"
            ]
        ),

        industry=(
            payload.get(
                "industry"
            )
        ),

        city=(
            payload.get(
                "city"
            )
        ),

        county=(
            payload.get(
                "county"
            )
        ),

        state=(
            payload.get(
                "state"
            )
        ),

        asking_price=(
            _to_decimal(
                payload[
                    "asking_price"
                ]
            )
            if payload.get(
                "asking_price"
            )
            is not None
            else None
        ),

        sde=(
            _to_decimal(
                payload[
                    "sde"
                ]
            )
            if payload.get(
                "sde"
            )
            is not None
            else None
        ),

        owner_hours=float(
            payload[
                "owner_hours"
            ]
        ),

        transition_training_days=float(
            payload[
                "transition_training_days"
            ]
        ),

        deal_preference=str(
            payload[
                "deal_preference"
            ]
        ),

        arr=_to_decimal(
            payload[
                "arr"
            ]
        ),

        largest_customer_percent=float(
            payload[
                "largest_customer_percent"
            ]
        ),

        years_in_operation=(
            int(
                payload[
                    "years_in_operation"
                ]
            )
            if payload.get(
                "years_in_operation"
            )
            is not None
            else None
        ),
    )


# ============================================================
# CELERY MATCHING TASK
# ============================================================


@celery_app.task(
    bind=True,
    name=(
        "app.matching.tasks."
        "rank_matches_task"
    ),
    autoretry_for=(
        TimeoutError,
        ConnectionError,
    ),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def rank_matches_task(
    self,
    buyer_payload: dict[
        str,
        Any,
    ],
    business_payloads: list[
        dict[
            str,
            Any,
        ]
    ],
    minimum_threshold: float = (
        DEFAULT_MIN_FIT_THRESHOLD
    ),
    top_n: int = (
        DEFAULT_TOP_N_MATCHES
    ),
) -> list[
    dict[
        str,
        Any,
    ]
]:
    """
    Asynchronously evaluate and rank businesses for one buyer.

    Current integration boundary:
        JSON-safe buyer/business payloads
        -> Matching Engine

    Future production boundary:
        buyer_id/event
        -> PostgreSQL repository
        -> Matching Engine
        -> persisted Match records
        -> Redis cache
    """

    buyer = _build_buyer_input(
        buyer_payload
    )

    businesses = [
        _build_business_input(
            payload
        )
        for payload
        in business_payloads
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

    results = [
        asdict(
            ranked_match
        )
        for ranked_match
        in ranked
    ]

    # Redis is only a cache.
    # A Redis outage must not invalidate
    # a successful Matching Engine result.
    try:
        cache = (
            get_match_cache()
        )

        cache.set_ranked_matches(
            buyer.buyer_id,
            results,
        )

    except RedisError:
        logger.warning(
            "Unable to cache matching results "
            "for buyer_id=%s",
            buyer.buyer_id,
            exc_info=True,
        )

    return results