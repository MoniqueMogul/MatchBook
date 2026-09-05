from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

from app.matching.db_service import (
    MatchingDatabaseServiceError,
)

from app.matching.repository import (
    MatchingDataIncompleteError,
)

from app.matching.schemas import (
    DimensionScore,
    MatchEvaluation,
    RankedMatch,
)


# ============================================================
# TEST CLIENT
# ============================================================


client = TestClient(
    app
)


# ============================================================
# TEST DATABASE SESSION
# ============================================================


@pytest.fixture
def fake_session():
    """
    Fake SQLAlchemy session used by the FastAPI dependency.

    No real PostgreSQL/Supabase connection is made.
    """

    session = Mock()

    def override_get_db():
        yield session

    app.dependency_overrides[
        get_db
    ] = override_get_db

    yield session

    app.dependency_overrides.clear()


# ============================================================
# TEST MATCH RESULT
# ============================================================


def make_ranked_match(
    *,
    buyer_id=None,
    business_id=None,
    rank: int = 1,
    score: float = 1.0,
) -> RankedMatch:
    """
    Build one deterministic ranked match for route testing.
    """

    buyer_id = (
        buyer_id
        or uuid4()
    )

    business_id = (
        business_id
        or uuid4()
    )

    dimensions = {
        "industry": DimensionScore(
            score=1.0,
            weight=0.0,
            contribution=0.0,
        ),

        "geography": DimensionScore(
            score=1.0,
            weight=0.0,
            contribution=0.0,
        ),

        "purchase_price": DimensionScore(
            score=1.0,
            weight=0.30,
            contribution=0.30,
        ),

        "sde": DimensionScore(
            score=1.0,
            weight=0.30,
            contribution=0.30,
        ),

        "owner_involvement": DimensionScore(
            score=1.0,
            weight=0.10,
            contribution=0.10,
        ),

        "transition_training": DimensionScore(
            score=1.0,
            weight=0.10,
            contribution=0.10,
        ),

        "deal_preference": DimensionScore(
            score=1.0,
            weight=0.10,
            contribution=0.10,
        ),

        "arr": DimensionScore(
            score=1.0,
            weight=0.05,
            contribution=0.05,
        ),

        "customer_concentration": DimensionScore(
            score=1.0,
            weight=0.05,
            contribution=0.05,
        ),
    }

    evaluation = MatchEvaluation(
        buyer_id=buyer_id,

        business_id=business_id,

        eligible=True,

        failed_constraints=[],

        score=score,

        percentage=(
            score
            * 100
        ),

        dimensions=dimensions,

        meets_threshold=True,
    )

    return RankedMatch(
        rank=rank,
        evaluation=evaluation,
    )


# ============================================================
# SUCCESSFUL DATABASE RECALCULATION
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_matches_success(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    business_id = uuid4()

    ranked_match = (
        make_ranked_match(
            buyer_id=buyer_id,
            business_id=business_id,
        )
    )

    mock_recalculate.return_value = [
        ranked_match,
    ]

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
        )
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "buyer_id"
        ]
        == str(
            buyer_id
        )
    )

    assert (
        data[
            "count"
        ]
        == 1
    )

    assert (
        len(
            data[
                "matches"
            ]
        )
        == 1
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
            "eligible"
        ]
        is True
    )

    assert (
        data[
            "matches"
        ][
            0
        ][
            "evaluation"
        ][
            "score"
        ]
        == 1.0
    )

    assert (
        data[
            "matches"
        ][
            0
        ][
            "evaluation"
        ][
            "percentage"
        ]
        == 100.0
    )

    mock_recalculate.assert_called_once_with(
        fake_session,
        buyer_id,
        minimum_threshold=0.7,
        top_n=10,
    )


# ============================================================
# CUSTOM THRESHOLD + TOP N
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_forwards_threshold_and_top_n(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    mock_recalculate.return_value = []

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
            "?minimum_threshold=0.85"
            "&top_n=5"
        )
    )

    assert (
        response.status_code
        == 200
    )

    mock_recalculate.assert_called_once_with(
        fake_session,
        buyer_id,
        minimum_threshold=0.85,
        top_n=5,
    )


# ============================================================
# EMPTY RESULT
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_returns_empty_match_list(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    mock_recalculate.return_value = []

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
        )
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()
        == {
            "buyer_id": str(
                buyer_id
            ),
            "count": 0,
            "matches": [],
        }
    )


# ============================================================
# MULTIPLE MATCHES
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_returns_multiple_ranked_matches(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    first_business = uuid4()

    second_business = uuid4()

    mock_recalculate.return_value = [
        make_ranked_match(
            buyer_id=buyer_id,
            business_id=first_business,
            rank=1,
            score=0.95,
        ),

        make_ranked_match(
            buyer_id=buyer_id,
            business_id=second_business,
            rank=2,
            score=0.85,
        ),
    ]

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
        )
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
            1
        ][
            "rank"
        ]
        == 2
    )

    assert (
        data[
            "matches"
        ][
            0
        ][
            "evaluation"
        ][
            "score"
        ]
        == 0.95
    )

    assert (
        data[
            "matches"
        ][
            1
        ][
            "evaluation"
        ][
            "score"
        ]
        == 0.85
    )


# ============================================================
# FASTAPI PATH VALIDATION
# ============================================================


def test_recalculate_rejects_invalid_buyer_uuid(
    fake_session,
):
    response = client.post(
        "/api/matches/recalculate/not-a-valid-uuid"
    )

    assert (
        response.status_code
        == 422
    )


# ============================================================
# QUERY VALIDATION
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_rejects_threshold_above_one(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
            "?minimum_threshold=1.1"
        )
    )

    assert (
        response.status_code
        == 422
    )

    mock_recalculate.assert_not_called()


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_rejects_negative_threshold(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
            "?minimum_threshold=-0.1"
        )
    )

    assert (
        response.status_code
        == 422
    )

    mock_recalculate.assert_not_called()


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_rejects_zero_top_n(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
            "?top_n=0"
        )
    )

    assert (
        response.status_code
        == 422
    )

    mock_recalculate.assert_not_called()


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_rejects_top_n_above_maximum(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
            "?top_n=101"
        )
    )

    assert (
        response.status_code
        == 422
    )

    mock_recalculate.assert_not_called()


# ============================================================
# INCOMPLETE MATCHING DATA
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_incomplete_data_returns_422(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    mock_recalculate.side_effect = (
        MatchingDataIncompleteError(
            "BuyerPreferences is missing preferred_arr"
        )
    )

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
        )
    )

    assert (
        response.status_code
        == 422
    )

    assert (
        "preferred_arr"
        in response.json()[
            "detail"
        ]
    )


# ============================================================
# SERVICE VALIDATION ERROR
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_value_error_returns_422(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    mock_recalculate.side_effect = (
        ValueError(
            "Invalid matching configuration"
        )
    )

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
        )
    )

    assert (
        response.status_code
        == 422
    )

    assert (
        response.json()[
            "detail"
        ]
        == "Invalid matching configuration"
    )


# ============================================================
# DATABASE SERVICE FAILURE
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_database_failure_returns_500(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    mock_recalculate.side_effect = (
        MatchingDatabaseServiceError(
            "database unavailable"
        )
    )

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
        )
    )

    assert (
        response.status_code
        == 500
    )

    assert (
        response.json()
        == {
            "detail": (
                "Unable to recalculate matches "
                "at this time."
            )
        }
    )


# ============================================================
# RESPONSE EXPLAINABILITY
# ============================================================


@patch(
    "app.matching.routes."
    "recalculate_matches_for_buyer"
)
def test_recalculate_returns_dimension_breakdown(
    mock_recalculate,
    fake_session,
):
    buyer_id = uuid4()

    ranked = make_ranked_match(
        buyer_id=buyer_id,
    )

    mock_recalculate.return_value = [
        ranked,
    ]

    response = client.post(
        (
            f"/api/matches/"
            f"recalculate/{buyer_id}"
        )
    )

    assert (
        response.status_code
        == 200
    )

    dimensions = (
        response.json()[
            "matches"
        ][
            0
        ][
            "evaluation"
        ][
            "dimensions"
        ]
    )

    assert (
        "purchase_price"
        in dimensions
    )

    assert (
        "sde"
        in dimensions
    )

    assert (
        "arr"
        in dimensions
    )

    assert (
        "customer_concentration"
        in dimensions
    )

    assert (
        dimensions[
            "purchase_price"
        ][
            "weight"
        ]
        == 0.30
    )

    assert (
        dimensions[
            "sde"
        ][
            "contribution"
        ]
        == 0.30
    )