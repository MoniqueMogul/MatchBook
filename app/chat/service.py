from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.repository import (
    ChatRepository,
    ConversationNotFoundError,
    MessageNotFoundError,
)
from app.chat.schema import MessageCreate, LatestMessageResponse, ConversationResponse, ConversationParticipantResponse, \
    ConversationBusinessResponse
from app.db.db_enum import EventType
from app.db.db_model import (
    Business,
    BuyerProfile,
    Conversation,
    Match,
    Message,
    SellerProfile,
    OutboxEvent,
)

from app.events.payload_schema import MessageCreatedPayload
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate


class ChatServiceError(Exception):
    """Base exception for chat services errors."""


class ChatAccessDeniedError(ChatServiceError):
    """Raised when a user is not part of the conversation."""


class MessageReadForbiddenError(ChatServiceError):
    """Raised when a sender tries to mark their own message as read."""


class ChatService:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session
        self.repository = ChatRepository(session)

    def list_conversations(
            self,
            user_id: UUID,
    ) -> list[ConversationResponse]:

        rows = self.repository.list_user_conversations(
            user_id=user_id,
        )

        conversations: list[ConversationResponse] = []

        for conversation, latest_message, unread_count in rows:
            match = conversation.match
            business = match.business

            # The participant is always the OTHER person.
            if match.buyer.user_id == user_id:
                participant = business.seller.user
            else:
                participant = match.buyer.user

            latest_message_response = None

            if latest_message is not None:
                latest_message_response = LatestMessageResponse(
                    id=latest_message.id,
                    sender_id=latest_message.sender_id,
                    content=latest_message.content,
                    created_at=latest_message.created_at,
                )

            conversations.append(
                ConversationResponse(
                    id=conversation.id,
                    match_id=conversation.match_id,

                    participant=ConversationParticipantResponse(
                        user_id=participant.id,
                        first_name=participant.first_name,
                        last_name=participant.last_name,
                    ),

                    business=ConversationBusinessResponse(
                        id=business.id,
                        legal_name=business.legal_name,
                        dba=business.dba,
                        industry=business.industry,
                        city=business.city,
                        state=business.state,
                    ),

                    latest_message=latest_message_response,
                    unread_count=unread_count,

                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                )
            )

        return conversations

    def get_messages(
        self,
        *,
        conversation_id: UUID,
        user_id: UUID,
    ) -> list[Message]:
        self._require_conversation_access(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return self.repository.get_messages(
            conversation_id=conversation_id,
        )

    def send_message(
            self,
            *,
            conversation_id: UUID,
            user_id: UUID,
            data: MessageCreate,
    ) -> tuple[Message, OutboxEvent]:

        conversation = self._require_conversation_access(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        match = conversation.match

        message = self.repository.create_message(
            conversation_id=conversation_id,
            sender_id=user_id,
            content=data.content,
        )

        recipient_user_id = self._get_recipient_user_id(
            match=match,
            sender_id=user_id,
        )

        payload = MessageCreatedPayload(
            recipient_user_id=recipient_user_id,
            conversation_id=conversation.id,
        )

        outbox_repository = OutboxRepository(
            self.session
        )

        outbox_event = outbox_repository.create_event(
            OutboxEventCreate(
                idempotency_key=f"message_created:{message.id}",
                event_type=EventType.MESSAGE_CREATED,
                entity_type="message",
                entity_id=message.id,
                payload=payload.model_dump(mode="json"),
            )
        )

        return message, outbox_event

    def mark_message_as_read(
        self,
        *,
        message_id: UUID,
        user_id: UUID,
    ) -> Message:
        message = self.repository.require_message(
            message_id
        )

        self._require_conversation_access(
            conversation_id=message.conversation_id,
            user_id=user_id,
        )

        # Only the recipient should mark a message as read.
        if message.sender_id == user_id:
            raise MessageReadForbiddenError(
                "You cannot mark your own message as read."
            )

        return self.repository.mark_message_as_read(
            message_id
        )

    def create_conversation(
        self,
        *,
        match_id: UUID,
        user_id: UUID,
    ) -> Conversation:
        self._require_match_access(
            match_id=match_id,
            user_id=user_id,
        )

        existing = self.repository.get_conversation_by_match(
            match_id=match_id,
        )

        if existing is not None:
            return existing

        return self.repository.create_conversation(
            match_id=match_id,
        )

    def _require_conversation_access(
        self,
        *,
        conversation_id: UUID,
        user_id: UUID,
    ) -> Conversation:
        conversation = self.repository.require_conversation(
            conversation_id
        )

        self._require_match_access(
            match_id=conversation.match_id,
            user_id=user_id,
        )

        return conversation

    def _require_match_access(
        self,
        *,
        match_id: UUID,
        user_id: UUID,
    ) -> Match:
        statement = (
            select(Match)
            .join(
                BuyerProfile,
                Match.buyer_id == BuyerProfile.id,
            )
            .join(
                Business,
                Match.business_id == Business.id,
            )
            .join(
                SellerProfile,
                Business.seller_id == SellerProfile.id,
            )
            .where(
                Match.id == match_id,
                (
                    (BuyerProfile.user_id == user_id)
                    | (SellerProfile.user_id == user_id)
                ),
            )
        )

        match = self.session.scalar(statement)

        if match is None:
            raise ChatAccessDeniedError(
                "You do not have access to this conversation."
            )

        return match


    #------------------------
    #------HELPER
    #------------------------
    def _get_recipient_user_id(
            self,
            *,
            match: Match,
            sender_id: UUID,
    ) -> UUID:

        buyer_user_id = match.buyer.user_id
        seller_user_id = match.business.seller.user_id

        if sender_id == buyer_user_id:
            return seller_user_id

        if sender_id == seller_user_id:
            return buyer_user_id

        raise ChatAccessDeniedError(
            "User is not part of this match."
        )