# app/events/router.py

from app.core.celery_app import celery_app
from app.db.db_enum import EventType


def publish_event(
    *,
    event_type: EventType,
    message: dict,
) -> None:

    published = False

    # ----------------------------------------------------
    # MATCHING
    # ----------------------------------------------------

    if event_type in {
        EventType.BUYER_PREFERENCES_UPDATED,
        EventType.BUSINESS_CREATED,
        EventType.BUSINESS_UPDATED,
    }:
        celery_app.send_task(
            "app.matching.tasks.process_matching_event_task",
            kwargs={
                "event_id": message["event_id"],
            },
            queue="matching",
        )

        published = True

    # ----------------------------------------------------
    # NOTIFICATIONS
    # ----------------------------------------------------

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
            kwargs={"event": message},
            queue="notifications",
        )

        published = True

    # ----------------------------------------------------
    # CHAT
    # ----------------------------------------------------

    if event_type == EventType.NDA_COMPLETED:
        celery_app.send_task(
            "app.chat.tasks.process_chat_event",
            kwargs={"event": message},
            queue="chat",
        )

        published = True

    # ----------------------------------------------------
    # NO CONSUMER
    # ----------------------------------------------------

    if not published:
        raise ValueError(
            f"No consumer configured for event type: "
            f"{event_type.value}"
        )