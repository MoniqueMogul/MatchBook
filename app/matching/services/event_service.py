from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import EventConsumer, EventType
from app.events.repository import OutboxRepository
from app.matching.db_service import (
    recalculate_matches_for_business,
    recalculate_matches_for_buyer,
)


def _event_id(event: dict[str, Any]) -> UUID:
    raw_event_id = event.get("event_id")

    if raw_event_id is None:
        raise ValueError("Event is missing event_id")

    return UUID(str(raw_event_id))


def _event_uuid(
    event: dict[str, Any],
    payload_key: str,
) -> UUID:
    payload = event.get("payload") or {}

    raw_id = (
        payload.get(payload_key)
        or event.get("entity_id")
    )

    if raw_id is None:
        raise ValueError(
            f"Event is missing {payload_key} and entity_id"
        )

    return UUID(str(raw_id))


def process_matching_event_service(
    *,
    session: Session,
    event: dict[str, Any],
) -> dict[str, Any]:

    event_id = _event_id(event)

    outbox_repository = OutboxRepository(session)

    outbox_repository.require_event(event_id)

    if outbox_repository.is_processed(
        event_id=event_id,
        consumer=EventConsumer.MATCHING,
    ):
        return {
            "status": "already_processed",
            "event_id": str(event_id),
        }

    event_type = EventType(event["event_type"])

    if event_type == EventType.BUYER_CREATED:
        buyer_id = _event_uuid(
            event,
            "buyer_id",
        )

        ranked_matches = recalculate_matches_for_buyer(
            session,
            buyer_id,
            commit=False,
        )

        result = {
            "status": "processed",
            "event_id": str(event_id),
            "event_type": event_type.value,
            "buyer_id": str(buyer_id),
            "match_count": len(ranked_matches),
        }

    elif event_type == EventType.BUSINESS_CREATED:
        business_id = _event_uuid(
            event,
            "business_id",
        )

        buyer_results = recalculate_matches_for_business(
            session,
            business_id,
            commit=False,
        )

        result = {
            "status": "processed",
            "event_id": str(event_id),
            "event_type": event_type.value,
            "business_id": str(business_id),
            "buyers_processed": len(buyer_results),
            "match_count": sum(
                len(matches)
                for matches in buyer_results.values()
            ),
        }

    else:
        raise ValueError(
            f"Unsupported matching event: {event_type.value}"
        )

    outbox_repository.mark_processed(
        event_id=event_id,
        consumer=EventConsumer.MATCHING,
    )

    return result