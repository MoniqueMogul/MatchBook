from __future__ import annotations

from uuid import UUID

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.db_enum import EventConsumer
from app.events.repository import OutboxRepository
from app.notification.handlers import handle_notification_event
from app.notification.repository import NotificationRepository


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={
        "max_retries": 5,
    },
)
def process_notification_event(
    event: dict,
) -> None:
    session = SessionLocal()

    try:
        outbox_repository = OutboxRepository(
            session
        )

        notification_repository = NotificationRepository(
            session
        )

        event_id = UUID(
            event["event_id"]
        )

        outbox_repository.require_event(
            event_id
        )

        if outbox_repository.is_processed(
            event_id=event_id,
            consumer=EventConsumer.NOTIFICATION,
        ):
            return

        handle_notification_event(
            event=event,
            repository=notification_repository,
        )

        outbox_repository.mark_processed(
            event_id=event_id,
            consumer=EventConsumer.NOTIFICATION,
        )

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()