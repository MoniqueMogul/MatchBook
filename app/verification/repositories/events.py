from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import EventType
from app.db.db_model import OutboxEvent
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate
from app.events.tasks import send_outbox_event


def publish_event(
    db: Session,
    event_type: EventType,
    entity_type: str,
    entity_id: UUID,
    payload: Optional[dict[str, Any]] = None,
) -> OutboxEvent:
    event = OutboxRepository(db).create_event(
        OutboxEventCreate(
            idempotency_key=f"{event_type.value}:{entity_type}:{entity_id}",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
        )
    )
    db.commit()
    db.refresh(event)

    send_outbox_event.delay(str(event.id))
    return event