from __future__ import annotations

from uuid import UUID

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.db_enum import OutboxStatus, EventType
from app.events.repository import OutboxRepository
from app.events.router import publish_event
from app.events.failure import OutboxFailure

import logging

log = logging.getLogger("matchbook.outbox")


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def send_outbox_event(event_id: str) -> None:
    session = SessionLocal()

    try:
        repository = OutboxRepository(session)

        event = repository.require_event(
            UUID(event_id)
        )

        if event.status != OutboxStatus.PENDING:
            return

        event_type = EventType(
            event.event_type
        )

        message = {
            "event_id": str(event.id),
            "idempotency_key": event.idempotency_key,
            "event_type": event_type.value,
            "entity_type": event.entity_type,
            "entity_id": str(event.entity_id),
            "payload": event.payload,
        }

        publish_event(
            event_type=event_type,
            message=message,
        )

        repository.mark_published(event)

        session.commit()


    except Exception as exc:

        failure = OutboxFailure.from_exception(exc)

        log.error(

            "outbox_publish_failed",

            extra={

                "event": "outbox_publish_failed",

                "event_id": event_id,

                "error_type": failure.exception_type,

            },

        )

        session.rollback()

        _record_publish_failure(

            event_id=event_id,

            failure=failure,

        )

        raise

    finally:
        session.close()

def _record_publish_failure(
        *,
        event_id: str,
        failure: OutboxFailure,
) -> None:

    session = SessionLocal()

    try:

        repository = OutboxRepository(session)

        event = repository.require_event(UUID(event_id))

        repository.mark_publish_failed(

            event,

            failure=failure,

        )

        session.commit()


    except Exception:

        session.rollback()

        raise

    finally:

        session.close()


@celery_app.task
def retry_pending_outbox_events() -> None:
    session = SessionLocal()

    try:
        repository = OutboxRepository(session)

        pending_events = repository.list_pending_events(
            limit=100
        )

        for event in pending_events:
            send_outbox_event.delay(
                str(event.id)
            )

    finally:
        session.close()