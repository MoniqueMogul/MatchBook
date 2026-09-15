from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=5000,
    )


class MessageResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    conversation_id: UUID
    sender_id: UUID
    content: str
    created_at: datetime
    read_at: datetime | None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    match_id: UUID
    created_at: datetime
    updated_at: datetime