# app/events/router.py

from app.core.celery_app import celery_app
from app.db.db_enum import EventType


def publish_event(
    *,
    event_type: EventType,
    message: dict,
) -> None:

    if event_type in {
        EventType.BUYER_CREATED,
        EventType.BUSINESS_CREATED,
    }:
        celery_app.send_task(
            "app.matching.tasks.process_matching_event",
            kwargs={
                "event": message,
            },
            queue="matching",
        )
        return

    if event_type in {
        EventType.MATCH_CREATED,
        EventType.MATCH_STATUS_CHANGED,
        EventType.VERIFICATION_COMPLETED,
        EventType.NDA_COMPLETED,
        EventType.DOCUMENT_UPLOADED,
        EventType.MESSAGE_CREATED,
    }:
        celery_app.send_task(
            "app.notification.tasks.process_notification_event",
            kwargs={
                "event": message,
            },
            queue="notifications",
        )
        return

    raise ValueError(
        f"No consumer configured for event type: "
        f"{event_type.value}"
    )