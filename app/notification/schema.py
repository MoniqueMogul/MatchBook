from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.db_enum import NotificationType


class NotificationResponse(BaseModel):
    id: UUID
    type: NotificationType
    title: str
    message: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime



class NotificationCreate(BaseModel):
    type: NotificationType

    title: str = Field(
        min_length=1,
        max_length=255,
    )

    message: str = Field(
        min_length=1,
    )

    related_entity_type: str | None = Field(
        default=None,
        max_length=50,
    )

    related_entity_id: UUID | None = None