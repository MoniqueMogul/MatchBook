from __future__ import annotations

from uuid import UUID

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.db_enum import OutboxStatus
from app.events.repository import OutboxRepository
from app.events.router import publish_event


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={
        "max_retries": 5,
    },
)
def send_outbox_event(
    event_id: str,
) -> None:
    """
    Publish a pending Outbox event to the appropriate
    downstream Celery consumer.

    The Outbox event remains PENDING when publishing fails.

    It is marked PUBLISHED only after Celery accepts
    the downstream task.
    """

    session = SessionLocal()

    try:
        repository = OutboxRepository(
            session
        )

        event = repository.require_event(
            UUID(event_id)
        )

        if event.status != OutboxStatus.PENDING:
            return

        message = {
            "event_id": str(event.id),
            "idempotency_key": event.idempotency_key,
            "event_type": event.event_type.value,
            "entity_type": event.entity_type,
            "entity_id": str(event.entity_id),
            "payload": event.payload,
        }

        publish_event(
            event_type=event.event_type,
            message=message,
        )

        repository.mark_published(
            event
        )

        session.commit()

    except Exception as exc:
        session.rollback()

        _record_publish_failure(
            event_id=event_id,
            error=str(exc),
        )

        raise

    finally:
        session.close()


def _record_publish_failure(
    *,
    event_id: str,
    error: str,
) -> None:
    """
    Record publishing failure in a separate transaction.

    The original transaction was rolled back, so we need
    a new transaction to persist the failure metadata.
    """

    session = SessionLocal()

    try:
        repository = OutboxRepository(
            session
        )

        event = repository.require_event(
            UUID(event_id)
        )

        repository.mark_publish_failed(
            event,
            error=error,
        )

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()
