from __future__ import annotations

from uuid import UUID

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.db_enum import OutboxStatus
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
    """
    Consume an event and create the corresponding notification.

    This worker owns the transaction.

    If the event has already been processed, it returns without
    creating another notification.
    """

    session = SessionLocal()

    try:
        outbox_repository = OutboxRepository(
            session
        )

        notification_repository = NotificationRepository(
            session
        )

        outbox_event = outbox_repository.require_event(
            UUID(event["event_id"])
        )

        # ----------------------------------------------------
        # Consumer idempotency
        # ----------------------------------------------------

        if outbox_event.status == OutboxStatus.PROCESSED:
            return

        # ----------------------------------------------------
        # Notification business logic
        # ----------------------------------------------------

        handle_notification_event(
            event=event,
            repository=notification_repository,
        )

        # ----------------------------------------------------
        # Record successful processing
        # ----------------------------------------------------

        outbox_repository.mark_processed(
            outbox_event
        )

        # Notification creation + processed state are committed
        # together.
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()