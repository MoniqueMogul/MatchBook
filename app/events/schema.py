from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.db_enum import EventType, OutboxStatus


class OutboxEventCreate(BaseModel):
    """
    Data required to create an Outbox event.
    """

    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
    )

    event_type: EventType

    entity_type: str = Field(
        min_length=1,
        max_length=50,
    )

    entity_id: UUID

    payload: dict


class OutboxEventResponse(BaseModel):
    """
    API/internal representation of an Outbox event.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    idempotency_key: str
    event_type: EventType
    entity_type: str
    entity_id: UUID
    payload: dict
    status: OutboxStatus
    attempt_count: int
    last_error: str | None
    created_at: datetime
    published_at: datetime | None
    processed_at: datetime | None