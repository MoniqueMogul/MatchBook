from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.db_enum import OutboxStatus
from app.db.db_model import OutboxEvent
from app.events.schema import OutboxEventCreate


class OutboxRepositoryError(Exception):
    """
    Base exception for expected Outbox persistence failures.
    """


class OutboxNotFoundError(OutboxRepositoryError):
    """
    Raised when an Outbox event does not exist.
    """


class OutboxRepository:
    """
    Persistence boundary for Outbox events.

    This repository performs database reads and writes.

    It deliberately does NOT commit or rollback.

    Transaction ownership belongs to the calling
    service or worker.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.session = session

    # ========================================================
    # CREATE
    # ========================================================

    def create_event(
        self,
        data: OutboxEventCreate,
    ) -> OutboxEvent:

        event = OutboxEvent(
            **data.model_dump(),
        )

        self.session.add(
            event
        )

        self.session.flush()

        return event

    # ========================================================
    # READ
    # ========================================================

    def get_event(
        self,
        event_id: UUID,
    ) -> OutboxEvent | None:

        return self.session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.id == event_id
            )
        )

    def require_event(
        self,
        event_id: UUID,
    ) -> OutboxEvent:

        event = self.get_event(
            event_id
        )

        if event is None:
            raise OutboxNotFoundError(
                f"Outbox event {event_id} does not exist."
            )

        return event

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> OutboxEvent | None:

        return self.session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.idempotency_key
                == idempotency_key
            )
        )

    # ========================================================
    # POLLING
    # ========================================================

    def list_pending_events(
        self,
        limit: int = 100,
    ) -> list[OutboxEvent]:

        statement = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status
                == OutboxStatus.PENDING
            )
            .order_by(
                OutboxEvent.created_at.asc()
            )
            .limit(
                limit
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    # ========================================================
    # STATE CHANGES
    # ========================================================

    def mark_published(
        self,
        event: OutboxEvent,
    ) -> OutboxEvent:

        event.status = OutboxStatus.PUBLISHED

        event.published_at = datetime.now(
            timezone.utc
        )

        event.last_error = None

        self.session.flush()

        return event

    def mark_processed(
        self,
        event: OutboxEvent,
    ) -> OutboxEvent:

        event.status = OutboxStatus.PROCESSED

        event.processed_at = datetime.now(
            timezone.utc
        )

        event.last_error = None

        self.session.flush()

        return event

    def mark_publish_failed(
        self,
        event: OutboxEvent,
        error: str,
    ) -> OutboxEvent:

        event.attempt_count += 1

        event.last_error = error

        self.session.flush()

        return event