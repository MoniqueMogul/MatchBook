from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.db_enum import EventConsumer, EventType
from app.db.db_model import OutboxEvent, ProcessedEvent
from app.matching.repository import MatchingRepository
from app.matching.service import match_buyer, match_business


class MatchingEventError(Exception):
    """Raised when a matching event cannot be processed."""


def process_matching_event(
    *,
    session: Session,
    event_id: UUID,
) -> None:
    """
    Process one outbox event for the Matching consumer.

    The caller owns commit / rollback.
    """

    event = session.scalar(
        select(OutboxEvent).where(
            OutboxEvent.id == event_id
        )
    )

    if event is None:
        raise MatchingEventError(
            f"Outbox event {event_id} does not exist."
        )

    # ----------------------------------------------------
    # IDEMPOTENCY
    # ----------------------------------------------------

    already_processed = session.scalar(
        select(ProcessedEvent.id).where(
            ProcessedEvent.event_id == event.id,
            ProcessedEvent.consumer == EventConsumer.MATCHING,
        )
    )

    if already_processed is not None:
        return

    repository = MatchingRepository(session)

    # ----------------------------------------------------
    # ROUTING
    # ----------------------------------------------------

    if (
        event.event_type
        == EventType.BUYER_PREFERENCES_UPDATED
    ):
        match_buyer(
            repository=repository,
            buyer_id=event.entity_id,
        )

    elif event.event_type in {
        EventType.BUSINESS_CREATED,
        EventType.BUSINESS_UPDATED,
    }:
        match_business(
            repository=repository,
            business_id=event.entity_id,
        )

    else:
        raise MatchingEventError(
            f"Unsupported matching event: "
            f"{event.event_type}"
        )

    # ----------------------------------------------------
    # MARK PROCESSED
    # ----------------------------------------------------

    session.add(
        ProcessedEvent(
            event_id=event.id,
            consumer=EventConsumer.MATCHING,
        )
    )