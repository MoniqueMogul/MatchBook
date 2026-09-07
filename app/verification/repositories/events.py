from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import EventType
from app.db.db_model import Event


def publish_event(
    db: Session,
    event_type: EventType,
    entity_type: str,
    entity_id: UUID,
    payload: Optional[dict[str, Any]] = None,
) -> Event:
    event = Event(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event