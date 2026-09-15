# app/events/router.py

from app.core.celery_app import celery_app
from app.db.db_enum import EventType


def publish_event(
    *,
    event_type: EventType,
    message: dict,
) -> None:

    published = False

    if event_type in {
        EventType.BUYER_CREATED,
        EventType.BUSINESS_CREATED,
    }:
        celery_app.send_task(
            "app.matching.tasks.process_matching_event",
            kwargs={"event": message},
            queue="matching",
        )

        published = True

    if event_type in {
        EventType.MATCH_CREATED,
        EventType.MATCH_STATUS_CHANGED,
        EventType.VERIFICATION_COMPLETED,
        EventType.NDA_COMPLETED,
        EventType.DOCUMENT_UPLOADED,
        EventType.MESSAGE_CREATED,
        EventType.DISCREPANCY_FLAGGED,
        EventType.VERIFICATION_REVIEW_REQUIRED,
    }:
        celery_app.send_task(
            "app.notification.tasks.process_notification_event",
            kwargs={"event": message},
            queue="notifications",
        )

        published = True

    if event_type == EventType.NDA_COMPLETED:
        celery_app.send_task(
            "app.chat.tasks.process_chat_event",
            kwargs={"event": message},
            queue="chat",
        )

        published = True

    if not published:
        raise ValueError(
            f"No consumer configured for event type: "
            f"{event_type.value}"
        )