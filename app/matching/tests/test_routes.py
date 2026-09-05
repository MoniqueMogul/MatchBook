from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.matching.routes import router


app = FastAPI()

app.include_router(
    router
)

client = TestClient(
    app
)


def buyer_payload() -> dict:
    return {
        "buyer_id": 1,

        "target_industries": [
            "HVAC",
        ],

        "target_locations": {
            "state": "Florida",
        },

        "maximum_purchase_price": "500000",

        "minimum_sde": "100000",

        "preferred_sde": "200000",

        "preferred_owner_hours": 20,

        "required_training_days": 30,

        "deal_preference": "cash",

        "minimum_arr": "200000",

        "preferred_arr": "500000",

        "accepts_customer_concentration_above_25_percent": False,

        "minimum_years_in_operation": 3,
    }


def business_payload(
    *,
    business_id: int = 100,
) -> dict:
    return {
        "business_id": business_id,

        "industry": "HVAC",

        "city": "Orlando",

        "county": "Orange",

        "state": "Florida",

        "asking_price": "500000",

        "sde": "200000",

        "owner_hours": 20,

        "transition_training_days": 30,

        "deal_preference": "cash",

        "arr": "500000",

        "largest_customer_percent": 20,

        "years_in_operation": 10,
    }


# ============================================================
# HEALTH
# ============================================================


def test_matching_health():
    response = client.get(
        "/api/matches/health"
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()
        == {
            "status": "healthy",
            "service": "matching",
        }
    )


# ============================================================
# SINGLE MATCH EVALUATION
# ============================================================


def test_evaluate_perfect_match():
    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business_payload()
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "eligible"
        ]
        is True
    )

    assert (
        data[
            "score"
        ]
        == 1.0
    )

    assert (
        data[
            "percentage"
        ]
        == 100.0
    )

    assert (
        data[
            "meets_threshold"
        ]
        is True
    )

    assert (
        "arr"
        in data[
            "dimensions"
        ]
    )


def test_evaluate_rejects_industry_mismatch():
    business = (
        business_payload()
    )

    business[
        "industry"
    ] = "Plumbing"

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "eligible"
        ]
        is False
    )

    assert (
        "industry"
        in data[
            "failed_constraints"
        ]
    )

    assert (
        data[
            "score"
        ]
        is None
    )


def test_evaluate_rejects_arr_below_minimum():
    business = (
        business_payload()
    )

    business[
        "arr"
    ] = "199999"

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "eligible"
        ]
        is False
    )

    assert (
        "arr"
        in data[
            "failed_constraints"
        ]
    )


def test_evaluate_rejects_years_below_minimum():
    business = (
        business_payload()
    )

    business[
        "years_in_operation"
    ] = 2

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "eligible"
        ]
        is False
    )

    assert (
        "years_in_operation"
        in data[
            "failed_constraints"
        ]
    )


# ============================================================
# BOUNDARY TESTS THROUGH API
# ============================================================


def test_api_accepts_exact_price_ceiling():
    business = (
        business_payload()
    )

    business[
        "asking_price"
    ] = "575000"

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()[
            "eligible"
        ]
        is True
    )


def test_api_rejects_one_dollar_over_price_ceiling():
    business = (
        business_payload()
    )

    business[
        "asking_price"
    ] = "575001"

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "eligible"
        ]
        is False
    )

    assert (
        "purchase_price"
        in data[
            "failed_constraints"
        ]
    )


def test_api_accepts_sde_exact_minimum():
    business = (
        business_payload()
    )

    business[
        "sde"
    ] = "100000"

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()[
            "eligible"
        ]
        is True
    )


def test_api_rejects_sde_one_dollar_below_minimum():
    business = (
        business_payload()
    )

    business[
        "sde"
    ] = "99999"

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        "sde"
        in data[
            "failed_constraints"
        ]
    )


# ============================================================
# REQUEST VALIDATION
# ============================================================


def test_rejects_invalid_customer_concentration():
    business = (
        business_payload()
    )

    business[
        "largest_customer_percent"
    ] = 120

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business
            ),
        },
    )

    assert (
        response.status_code
        == 422
    )


def test_rejects_preferred_sde_below_minimum():
    buyer = (
        buyer_payload()
    )

    buyer[
        "minimum_sde"
    ] = "200000"

    buyer[
        "preferred_sde"
    ] = "100000"

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer
            ),
            "business": (
                business_payload()
            ),
        },
    )

    assert (
        response.status_code
        == 422
    )


def test_rejects_preferred_arr_below_minimum():
    buyer = (
        buyer_payload()
    )

    buyer[
        "minimum_arr"
    ] = "500000"

    buyer[
        "preferred_arr"
    ] = "200000"

    response = client.post(
        "/api/matches/evaluate",
        json={
            "buyer": (
                buyer
            ),
            "business": (
                business_payload()
            ),
        },
    )

    assert (
        response.status_code
        == 422
    )


def test_rejects_invalid_threshold():
    response = client.post(
        "/api/matches/evaluate"
        "?minimum_threshold=1.5",
        json={
            "buyer": (
                buyer_payload()
            ),
            "business": (
                business_payload()
            ),
        },
    )

    assert (
        response.status_code
        == 422
    )


# ============================================================
# RANKING ENDPOINT
# ============================================================


def test_rank_matches_orders_candidates():
    excellent = (
        business_payload(
            business_id=1
        )
    )

    medium = (
        business_payload(
            business_id=2
        )
    )

    medium[
        "asking_price"
    ] = "530000"

    medium[
        "sde"
    ] = "150000"

    medium[
        "owner_hours"
    ] = 25

    medium[
        "transition_training_days"
    ] = 20

    medium[
        "arr"
    ] = "350000"

    response = client.post(
        "/api/matches/rank"
        "?minimum_threshold=0"
        "&top_n=10",
        json={
            "buyer": (
                buyer_payload()
            ),
            "businesses": [
                medium,
                excellent,
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "count"
        ]
        == 2
    )

    assert (
        data[
            "matches"
        ][
            0
        ][
            "rank"
        ]
        == 1
    )

    assert (
        data[
            "matches"
        ][
            0
        ][
            "evaluation"
        ][
            "business_id"
        ]
        == 1
    )


def test_rank_endpoint_excludes_ineligible_candidate():
    good = (
        business_payload(
            business_id=1
        )
    )

    bad = (
        business_payload(
            business_id=2
        )
    )

    bad[
        "industry"
    ] = "Plumbing"

    response = client.post(
        "/api/matches/rank"
        "?minimum_threshold=0",
        json={
            "buyer": (
                buyer_payload()
            ),
            "businesses": [
                bad,
                good,
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "count"
        ]
        == 1
    )

    assert (
        data[
            "matches"
        ][
            0
        ][
            "evaluation"
        ][
            "business_id"
        ]
        == 1
    )


def test_rank_endpoint_respects_top_n():
    businesses = [
        business_payload(
            business_id=index
        )
        for index
        in range(
            1,
            11,
        )
    ]

    response = client.post(
        "/api/matches/rank"
        "?minimum_threshold=0"
        "&top_n=5",
        json={
            "buyer": (
                buyer_payload()
            ),
            "businesses": (
                businesses
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "count"
        ]
        == 5
    )

    assert (
        len(
            data[
                "matches"
            ]
        )
        == 5
    )


def test_rank_endpoint_rejects_zero_top_n():
    response = client.post(
        "/api/matches/rank"
        "?top_n=0",
        json={
            "buyer": (
                buyer_payload()
            ),
            "businesses": [
                business_payload()
            ],
        },
    )

    assert (
        response.status_code
        == 422
    )