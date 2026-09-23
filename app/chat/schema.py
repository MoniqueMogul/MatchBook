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


class ConversationParticipantResponse(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str


class ConversationBusinessResponse(BaseModel):
    id: UUID
    legal_name: str | None
    dba: str | None
    industry: str
    city: str
    state: str


class LatestMessageResponse(BaseModel):
    id: UUID
    sender_id: UUID
    content: str
    created_at: datetime


class ConversationResponse(BaseModel):
    id: UUID
    match_id: UUID

    participant: ConversationParticipantResponse
    business: ConversationBusinessResponse

    latest_message: LatestMessageResponse | None
    unread_count: int

    created_at: datetime
    updated_at: datetime