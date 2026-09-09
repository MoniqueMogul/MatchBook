from unittest.mock import patch

from app.core.celery_app import celery_app
from app.db.db_enum import EventType
from app.events.router import publish_event


def test_buyer_created_routes_to_matching_queue() -> None:

    message = {
        "event_type": "buyer_created",
        "entity_type": "buyer",
        "entity_id": "buyer-123",
        "payload": {
            "buyer_id": "buyer-123",
        },
    }

    with patch.object(
        celery_app,
        "send_task",
    ) as send_task:

        publish_event(
            event_type=EventType.BUYER_CREATED,
            message=message,
        )

    send_task.assert_called_once_with(
        "app.matching.tasks.process_matching_event",
        kwargs={
            "event": message,
        },
        queue="matching",
    )


def test_business_created_routes_to_matching_queue() -> None:

    message = {
        "event_type": "business_created",
        "entity_type": "business",
        "entity_id": "business-123",
        "payload": {
            "business_id": "business-123",
        },
    }

    with patch.object(
        celery_app,
        "send_task",
    ) as send_task:

        publish_event(
            event_type=EventType.BUSINESS_CREATED,
            message=message,
        )

    send_task.assert_called_once_with(
        "app.matching.tasks.process_matching_event",
        kwargs={
            "event": message,
        },
        queue="matching",
    )


def test_shared_celery_config_registers_matching_queue() -> None:

    queue_names = {
        queue.name
        for queue
        in celery_app.conf.task_queues
    }

    assert "matching" in queue_names

    routes = celery_app.conf.task_routes

    assert (
        routes[
            "app.matching.tasks.process_matching_event"
        ]["queue"]
        == "matching"
    )