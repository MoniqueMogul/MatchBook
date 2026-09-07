from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

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