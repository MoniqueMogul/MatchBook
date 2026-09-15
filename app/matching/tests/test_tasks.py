from uuid import UUID

import pytest

from unittest.mock import (
    Mock,
    patch,
)

from app.db.db_enum import EventConsumer

from app.matching.tasks import (
    _build_business_input,
    _build_buyer_input,
    process_matching_event,
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
):
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
# BUYER PAYLOAD
# ============================================================


def test_build_buyer_input():
    buyer = _build_buyer_input(
        buyer_payload()
    )

    assert buyer.buyer_id == 1

    assert (
        buyer.maximum_purchase_price
        is not None
    )

    assert (
        str(
            buyer.maximum_purchase_price
        )
        == "500000"
    )

    assert (
        buyer.minimum_arr
        is not None
    )

    assert (
        str(
            buyer.minimum_arr
        )
        == "200000"
    )

    assert (
        buyer.minimum_years_in_operation
        == 3
    )


# ============================================================
# BUSINESS PAYLOAD
# ============================================================


def test_build_business_input():
    business = _build_business_input(
        business_payload()
    )

    assert business.business_id == 100

    assert business.industry == "HVAC"

    assert (
        str(
            business.asking_price
        )
        == "500000"
    )

    assert (
        str(
            business.arr
        )
        == "500000"
    )

    assert (
        business.years_in_operation
        == 10
    )


# ============================================================
# ASYNC MATCH TASK
# ============================================================


@patch(
    "app.matching.tasks.get_match_cache"
)
def test_async_matching_task(
    mock_get_cache,
):
    fake_cache = Mock()

    mock_get_cache.return_value = (
        fake_cache
    )

    result = rank_matches_task.run(
        buyer_payload(),
        [
            business_payload(
                business_id=100
            )
        ],
        minimum_threshold=0.70,
        top_n=10,
    )

    assert len(result) == 1

    assert result[0]["rank"] == 1

    assert (
        result[0][
            "evaluation"
        ][
            "business_id"
        ]
        == 100
    )

    assert (
        result[0][
            "evaluation"
        ][
            "percentage"
        ]
        == 100.0
    )

    fake_cache.set_ranked_matches.assert_called_once()


@patch(
    "app.matching.tasks.get_match_cache"
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
            business_id=index
        )
        for index in range(
            1,
            11,
        )
    ]

    result = rank_matches_task.run(
        buyer_payload(),
        businesses,
        minimum_threshold=0.0,
        top_n=5,
    )

    assert len(result) == 5


@patch(
    "app.matching.tasks.get_match_cache"
)
def test_async_task_excludes_business_below_minimum_years(
    mock_get_cache,
):
    fake_cache = Mock()

    mock_get_cache.return_value = (
        fake_cache
    )

    business = business_payload(
        business_id=100
    )

    business[
        "years_in_operation"
    ] = 2

    result = rank_matches_task.run(
        buyer_payload(),
        [
            business
        ],
        minimum_threshold=0.0,
        top_n=10,
    )

    assert result == []


@patch(
    "app.matching.tasks.get_match_cache"
)
def test_async_task_excludes_business_below_minimum_arr(
    mock_get_cache,
):
    fake_cache = Mock()

    mock_get_cache.return_value = (
        fake_cache
    )

    business = business_payload(
        business_id=100
    )

    business[
        "arr"
    ] = "199999"

    result = rank_matches_task.run(
        buyer_payload(),
        [
            business
        ],
        minimum_threshold=0.0,
        top_n=10,
    )

    assert result == []


# ============================================================
# EVENT-DRIVEN MATCHING TESTS
# ============================================================


@patch(
    "app.matching.tasks."
    "recalculate_matches_for_buyer"
)
@patch(
    "app.matching.tasks."
    "OutboxRepository"
)
@patch(
    "app.matching.tasks."
    "SessionLocal"
)
def test_process_buyer_created_event(
    mock_session_local,
    mock_outbox_repository,
    mock_recalculate,
):
    event_id = UUID(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )

    buyer_id = UUID(
        "11111111-1111-1111-1111-111111111111"
    )

    fake_session = Mock()
    fake_outbox = Mock()

    mock_session_local.return_value = (
        fake_session
    )

    mock_outbox_repository.return_value = (
        fake_outbox
    )

    fake_outbox.is_processed.return_value = (
        False
    )

    mock_recalculate.return_value = [
        Mock(),
        Mock(),
    ]

    result = process_matching_event.run(
        {
            "event_id": str(
                event_id
            ),
            "event_type": (
                "buyer_created"
            ),
            "entity_id": str(
                buyer_id
            ),
            "payload": {
                "buyer_id": str(
                    buyer_id
                ),
            },
        }
    )

    mock_outbox_repository.assert_called_once_with(
        fake_session
    )

    fake_outbox.require_event.assert_called_once_with(
        event_id
    )

    fake_outbox.is_processed.assert_called_once_with(
        event_id=event_id,
        consumer=EventConsumer.MATCHING,
    )

    mock_recalculate.assert_called_once_with(
        fake_session,
        buyer_id,
        commit=False,
    )

    fake_outbox.mark_processed.assert_called_once_with(
        event_id=event_id,
        consumer=EventConsumer.MATCHING,
    )

    fake_session.commit.assert_called_once()

    fake_session.rollback.assert_not_called()

    fake_session.close.assert_called_once()

    assert result == {
        "status": "processed",
        "event_id": str(
            event_id
        ),
        "event_type": (
            "buyer_created"
        ),
        "buyer_id": str(
            buyer_id
        ),
        "match_count": 2,
    }


@patch(
    "app.matching.tasks."
    "recalculate_matches_for_business"
)
@patch(
    "app.matching.tasks."
    "OutboxRepository"
)
@patch(
    "app.matching.tasks."
    "SessionLocal"
)
def test_process_business_created_event(
    mock_session_local,
    mock_outbox_repository,
    mock_recalculate,
):
    event_id = UUID(
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )

    business_id = UUID(
        "22222222-2222-2222-2222-222222222222"
    )

    buyer_id = UUID(
        "33333333-3333-3333-3333-333333333333"
    )

    fake_session = Mock()
    fake_outbox = Mock()

    mock_session_local.return_value = (
        fake_session
    )

    mock_outbox_repository.return_value = (
        fake_outbox
    )

    fake_outbox.is_processed.return_value = (
        False
    )

    mock_recalculate.return_value = {
        buyer_id: [
            Mock(),
            Mock(),
            Mock(),
        ],
    }

    result = process_matching_event.run(
        {
            "event_id": str(
                event_id
            ),
            "event_type": (
                "business_created"
            ),
            "entity_id": str(
                business_id
            ),
            "payload": {
                "business_id": str(
                    business_id
                ),
            },
        }
    )

    fake_outbox.require_event.assert_called_once_with(
        event_id
    )

    fake_outbox.is_processed.assert_called_once_with(
        event_id=event_id,
        consumer=EventConsumer.MATCHING,
    )

    mock_recalculate.assert_called_once_with(
        fake_session,
        business_id,
        commit=False,
    )

    fake_outbox.mark_processed.assert_called_once_with(
        event_id=event_id,
        consumer=EventConsumer.MATCHING,
    )

    fake_session.commit.assert_called_once()

    fake_session.rollback.assert_not_called()

    fake_session.close.assert_called_once()

    assert result == {
        "status": "processed",
        "event_id": str(
            event_id
        ),
        "event_type": (
            "business_created"
        ),
        "business_id": str(
            business_id
        ),
        "buyers_processed": 1,
        "match_count": 3,
    }


@patch(
    "app.matching.tasks."
    "recalculate_matches_for_buyer"
)
@patch(
    "app.matching.tasks."
    "OutboxRepository"
)
@patch(
    "app.matching.tasks."
    "SessionLocal"
)
def test_process_matching_event_skips_duplicate(
    mock_session_local,
    mock_outbox_repository,
    mock_recalculate,
):
    event_id = UUID(
        "cccccccc-cccc-cccc-cccc-cccccccccccc"
    )

    buyer_id = UUID(
        "44444444-4444-4444-4444-444444444444"
    )

    fake_session = Mock()
    fake_outbox = Mock()

    mock_session_local.return_value = (
        fake_session
    )

    mock_outbox_repository.return_value = (
        fake_outbox
    )

    fake_outbox.is_processed.return_value = (
        True
    )

    result = process_matching_event.run(
        {
            "event_id": str(
                event_id
            ),
            "event_type": (
                "buyer_created"
            ),
            "entity_id": str(
                buyer_id
            ),
            "payload": {
                "buyer_id": str(
                    buyer_id
                ),
            },
        }
    )

    fake_outbox.require_event.assert_called_once_with(
        event_id
    )

    fake_outbox.is_processed.assert_called_once_with(
        event_id=event_id,
        consumer=EventConsumer.MATCHING,
    )

    mock_recalculate.assert_not_called()

    fake_outbox.mark_processed.assert_not_called()

    fake_session.commit.assert_not_called()

    fake_session.rollback.assert_not_called()

    fake_session.close.assert_called_once()

    assert result == {
        "status": "already_processed",
        "event_id": str(
            event_id
        ),
    }


@patch(
    "app.matching.tasks."
    "OutboxRepository"
)
@patch(
    "app.matching.tasks."
    "SessionLocal"
)
def test_process_matching_event_rejects_unknown_event(
    mock_session_local,
    mock_outbox_repository,
):
    event_id = UUID(
        "dddddddd-dddd-dddd-dddd-dddddddddddd"
    )

    fake_session = Mock()
    fake_outbox = Mock()

    mock_session_local.return_value = (
        fake_session
    )

    mock_outbox_repository.return_value = (
        fake_outbox
    )

    fake_outbox.is_processed.return_value = (
        False
    )

    with pytest.raises(
        ValueError
    ):
        process_matching_event.run(
            {
                "event_id": str(
                    event_id
                ),
                "event_type": (
                    "document_uploaded"
                ),
                "payload": {},
            }
        )

    fake_outbox.mark_processed.assert_not_called()

    fake_session.commit.assert_not_called()

    fake_session.rollback.assert_called_once()

    fake_session.close.assert_called_once()


@patch(
    "app.matching.tasks."
    "OutboxRepository"
)
@patch(
    "app.matching.tasks."
    "SessionLocal"
)
def test_process_matching_event_rejects_invalid_uuid(
    mock_session_local,
    mock_outbox_repository,
):
    event_id = UUID(
        "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    )

    fake_session = Mock()
    fake_outbox = Mock()

    mock_session_local.return_value = (
        fake_session
    )

    mock_outbox_repository.return_value = (
        fake_outbox
    )

    fake_outbox.is_processed.return_value = (
        False
    )

    with pytest.raises(
        ValueError,
        match="Invalid UUID",
    ):
        process_matching_event.run(
            {
                "event_id": str(
                    event_id
                ),
                "event_type": (
                    "buyer_created"
                ),
                "payload": {
                    "buyer_id": (
                        "not-a-valid-uuid"
                    ),
                },
            }
        )

    fake_outbox.mark_processed.assert_not_called()

    fake_session.commit.assert_not_called()

    fake_session.rollback.assert_called_once()

    fake_session.close.assert_called_once()


@patch(
    "app.matching.tasks."
    "recalculate_matches_for_buyer"
)
@patch(
    "app.matching.tasks."
    "OutboxRepository"
)
@patch(
    "app.matching.tasks."
    "SessionLocal"
)
def test_process_matching_event_rolls_back_on_matching_failure(
    mock_session_local,
    mock_outbox_repository,
    mock_recalculate,
):
    event_id = UUID(
        "ffffffff-ffff-ffff-ffff-ffffffffffff"
    )

    buyer_id = UUID(
        "55555555-5555-5555-5555-555555555555"
    )

    fake_session = Mock()
    fake_outbox = Mock()

    mock_session_local.return_value = (
        fake_session
    )

    mock_outbox_repository.return_value = (
        fake_outbox
    )

    fake_outbox.is_processed.return_value = (
        False
    )

    mock_recalculate.side_effect = (
        RuntimeError(
            "matching failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="matching failed",
    ):
        process_matching_event.run(
            {
                "event_id": str(
                    event_id
                ),
                "event_type": (
                    "buyer_created"
                ),
                "entity_id": str(
                    buyer_id
                ),
                "payload": {
                    "buyer_id": str(
                        buyer_id
                    ),
                },
            }
        )

    mock_recalculate.assert_called_once_with(
        fake_session,
        buyer_id,
        commit=False,
    )

    fake_outbox.mark_processed.assert_not_called()

    fake_session.commit.assert_not_called()

    fake_session.rollback.assert_called_once()

    fake_session.close.assert_called_once()