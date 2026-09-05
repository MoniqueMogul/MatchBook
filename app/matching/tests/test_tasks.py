from unittest.mock import (
    Mock,
    patch,
)

from app.matching.tasks import (
    _build_business_input,
    _build_buyer_input,
    rank_matches_task,
)


def buyer_payload():
    return {
        "buyer_id": 1,

        "target_industries": [
            "HVAC",
        ],

        "target_locations": {
            "state": "Florida",
        },

        "maximum_purchase_price": (
            "500000"
        ),

        "minimum_sde": (
            "100000"
        ),

        "preferred_sde": (
            "200000"
        ),

        "preferred_owner_hours": 20,

        "required_training_days": 30,

        "deal_preference": "cash",

        "minimum_arr": (
            "200000"
        ),

        "preferred_arr": (
            "500000"
        ),

        "accepts_customer_concentration_above_25_percent": False,

        "minimum_years_in_operation": 3,
    }


def business_payload(
    *,
    business_id: int = 100,
):
    return {
        "business_id": (
            business_id
        ),

        "industry": "HVAC",

        "city": "Orlando",

        "county": "Orange",

        "state": "Florida",

        "asking_price": (
            "500000"
        ),

        "sde": (
            "200000"
        ),

        "owner_hours": 20,

        "transition_training_days": 30,

        "deal_preference": "cash",

        "arr": (
            "500000"
        ),

        "largest_customer_percent": 20,

        "years_in_operation": 10,
    }


# ============================================================
# BUYER PAYLOAD
# ============================================================


def test_build_buyer_input():
    buyer = (
        _build_buyer_input(
            buyer_payload()
        )
    )

    assert (
        buyer.buyer_id
        == 1
    )

    assert (
        buyer.maximum_purchase_price
        is not None
    )

    assert str(
        buyer.maximum_purchase_price
    ) == "500000"

    assert (
        buyer.minimum_arr
        is not None
    )

    assert str(
        buyer.minimum_arr
    ) == "200000"

    assert (
        buyer.minimum_years_in_operation
        == 3
    )


# ============================================================
# BUSINESS PAYLOAD
# ============================================================


def test_build_business_input():
    business = (
        _build_business_input(
            business_payload()
        )
    )

    assert (
        business.business_id
        == 100
    )

    assert (
        business.industry
        == "HVAC"
    )

    assert str(
        business.asking_price
    ) == "500000"

    assert str(
        business.arr
    ) == "500000"

    assert (
        business.years_in_operation
        == 10
    )


# ============================================================
# ASYNC MATCH TASK
# ============================================================


@patch(
    "app.matching.tasks."
    "get_match_cache"
)
def test_async_matching_task(
    mock_get_cache,
):
    fake_cache = Mock()

    mock_get_cache.return_value = (
        fake_cache
    )

    result = (
        rank_matches_task.run(
            buyer_payload(),
            [
                business_payload(
                    business_id=100
                )
            ],
            minimum_threshold=0.70,
            top_n=10,
        )
    )

    assert (
        len(
            result
        )
        == 1
    )

    assert (
        result[
            0
        ][
            "rank"
        ]
        == 1
    )

    assert (
        result[
            0
        ][
            "evaluation"
        ][
            "business_id"
        ]
        == 100
    )

    assert (
        result[
            0
        ][
            "evaluation"
        ][
            "percentage"
        ]
        == 100.0
    )

    fake_cache.set_ranked_matches.assert_called_once()


@patch(
    "app.matching.tasks."
    "get_match_cache"
)
def test_async_task_respects_top_n(
    mock_get_cache,
):
    fake_cache = Mock()

    mock_get_cache.return_value = (
        fake_cache
    )

    businesses = [
        business_payload(
            business_id=(
                index
            )
        )
        for index
        in range(
            1,
            11,
        )
    ]

    result = (
        rank_matches_task.run(
            buyer_payload(),
            businesses,
            minimum_threshold=0.0,
            top_n=5,
        )
    )

    assert (
        len(
            result
        )
        == 5
    )


@patch(
    "app.matching.tasks."
    "get_match_cache"
)
def test_async_task_excludes_business_below_minimum_years(
    mock_get_cache,
):
    fake_cache = Mock()

    mock_get_cache.return_value = (
        fake_cache
    )

    business = (
        business_payload(
            business_id=100
        )
    )

    business[
        "years_in_operation"
    ] = 2

    result = (
        rank_matches_task.run(
            buyer_payload(),
            [
                business
            ],
            minimum_threshold=0.0,
            top_n=10,
        )
    )

    assert result == []


@patch(
    "app.matching.tasks."
    "get_match_cache"
)
def test_async_task_excludes_business_below_minimum_arr(
    mock_get_cache,
):
    fake_cache = Mock()

    mock_get_cache.return_value = (
        fake_cache
    )

    business = (
        business_payload(
            business_id=100
        )
    )

    business[
        "arr"
    ] = "199999"

    result = (
        rank_matches_task.run(
            buyer_payload(),
            [
                business
            ],
            minimum_threshold=0.0,
            top_n=10,
        )
    )

    assert result == []