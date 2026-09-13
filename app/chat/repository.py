from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.db_model import (
    Business,
    BuyerProfile,
    Conversation,
    Match,
    Message,
    SellerProfile,
)

class ChatRepositoryError(Exception):
    """Base exception for chat repository errors."""


class ConversationNotFoundError(ChatRepositoryError):
    """Raised when a conversation does not exist."""


class MessageNotFoundError(ChatRepositoryError):
    """Raised when a message does not exist."""


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_conversation(
        self,
        conversation_id: UUID,
    ) -> Conversation | None:
        return self.session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id
            )
        )

    def require_conversation(
        self,
        conversation_id: UUID,
    ) -> Conversation:
        conversation = self.get_conversation(
            conversation_id
        )

        if conversation is None:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} does not exist."
            )

        return conversation

    def get_conversation_by_match(
        self,
        match_id: UUID,
    ) -> Conversation | None:
        return self.session.scalar(
            select(Conversation).where(
                Conversation.match_id == match_id
            )
        )

    def create_conversation(
        self,
        match_id: UUID,
    ) -> Conversation:
        conversation = Conversation(
            match_id=match_id,
        )

        self.session.add(conversation)
        self.session.flush()

        return conversation

    def get_messages(
        self,
        conversation_id: UUID,
    ) -> list[Message]:
        statement = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id
            )
            .order_by(
                Message.created_at.asc()
            )
        )

        return list(
            self.session.scalars(statement).all()
        )

    def create_message(
        self,
        *,
        conversation_id: UUID,
        sender_id: UUID,
        content: str,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
        )

        self.session.add(message)
        self.session.flush()

        return message

    def get_message(
        self,
        message_id: UUID,
    ) -> Message | None:
        return self.session.scalar(
            select(Message).where(
                Message.id == message_id
            )
        )

    def require_message(
        self,
        message_id: UUID,
    ) -> Message:
        message = self.get_message(
            message_id
        )

        if message is None:
            raise MessageNotFoundError(
                f"Message {message_id} does not exist."
            )

        return message

    def mark_message_as_read(
        self,
        message_id: UUID,
    ) -> Message:
        message = self.require_message(
            message_id
        )

        if message.read_at is None:
            message.read_at = datetime.now(
                timezone.utc
            )

            self.session.flush()

        return message


def list_user_conversations(
    self,
    user_id: UUID,
) -> list[Conversation]:
    statement = (
        select(Conversation)
        .join(
            Match,
            Conversation.match_id == Match.id,
        )
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
            (BuyerProfile.user_id == user_id)
            | (SellerProfile.user_id == user_id)
        )
        .order_by(
            Conversation.updated_at.desc()
        )
    )

    return list(
        self.session.scalars(statement).all()
    )