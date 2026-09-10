from uuid import UUID
from pydantic import BaseModel

from app.db.db_enum import EventType


class EventEnvelope(BaseModel):
    event_type: EventType
    entity_type: str
    entity_id: UUID
    payload: dict


class MatchCreatedPayload(BaseModel):
    user_id: UUID
    match_id: UUID


class MatchStatusChangedPayload(BaseModel):
    user_id: UUID
    match_id: UUID
    status: str


class VerificationCompletedPayload(BaseModel):
    user_id: UUID
    verification_id: UUID


class NdaCompletedPayload(BaseModel):
    user_id: UUID
    nda_id: UUID


class DocumentUploadedPayload(BaseModel):
    user_id: UUID
    document_id: UUID


class MessageCreatedPayload(BaseModel):
    recipient_user_id: UUID
    conversation_id: UUID