# app/matching/event_service.py

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import EventConsumer, EventType
from app.events.repository import OutboxRepository
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

    outbox_repository = OutboxRepository(session)
    matching_repository = MatchingRepository(session)

    # ----------------------------------------------------
    # LOAD EVENT
    # ----------------------------------------------------

    event = outbox_repository.require_event(event_id)

    # ----------------------------------------------------
    # IDEMPOTENCY
    # ----------------------------------------------------

    if outbox_repository.is_processed(
            event_id=event.id,
            consumer=EventConsumer.MATCHING,
    ):
        return

    # ----------------------------------------------------
    # NORMALIZE EVENT TYPE
    # ----------------------------------------------------

    event_type = EventType(event.event_type)

    # ----------------------------------------------------
    # ROUTING
    # ----------------------------------------------------

    if event_type == EventType.BUYER_PREFERENCES_UPDATED:
        match_buyer(
            repository=matching_repository,
            buyer_id=event.entity_id,
        )

    elif event_type in {
        EventType.BUSINESS_CREATED,
        EventType.BUSINESS_UPDATED,
    }:
        match_business(
            repository=matching_repository,
            business_id=event.entity_id,
        )

    else:
        raise MatchingEventError(
            f"Unsupported matching event: {event_type.value}"
        )

    # ----------------------------------------------------
    # MARK PROCESSED
    # ----------------------------------------------------

    outbox_repository.mark_processed(
        event_id=event.id,
        consumer=EventConsumer.MATCHING,
    )
