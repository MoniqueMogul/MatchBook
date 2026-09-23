from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session, joinedload, selectinload, aliased

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



@dataclass(frozen=True)
class ConversationListItem:
    id: UUID
    match_id: UUID

    participant_user_id: UUID
    participant_first_name: str
    participant_last_name: str

    business_id: UUID
    business_name: str
    business_industry: str

    latest_message_id: UUID | None
    latest_message_sender_id: UUID | None
    latest_message_content: str | None
    latest_message_created_at: datetime | None

    unread_count: int

    category: str

    created_at: datetime
    updated_at: datetime


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
    ):
        LatestMessage = aliased(Message)

        latest_message_id = (
            select(Message.id)
            .where(
                Message.conversation_id == Conversation.id
            )
            .order_by(
                Message.created_at.desc(),
                Message.id.desc(),
            )
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )

        unread_count = (
            select(func.count(Message.id))
            .where(
                Message.conversation_id == Conversation.id,
                Message.sender_id != user_id,
                Message.read_at.is_(None),
            )
            .correlate(Conversation)
            .scalar_subquery()
        )

        stmt = (
            select(
                Conversation,
                LatestMessage,
                unread_count.label("unread_count"),
            )
            .join(Conversation.match)
            .join(Match.buyer)
            .join(Match.business)
            .join(Business.seller)
            .outerjoin(
                LatestMessage,
                LatestMessage.id == latest_message_id,
            )
            .where(
                or_(
                    BuyerProfile.user_id == user_id,
                    SellerProfile.user_id == user_id,
                )
            )
            .options(
                joinedload(Conversation.match)
                .joinedload(Match.buyer)
                .joinedload(BuyerProfile.user),

                joinedload(Conversation.match)
                .joinedload(Match.business)
                .joinedload(Business.seller)
                .joinedload(SellerProfile.user),
            )
            .order_by(Conversation.updated_at.desc())
        )

        return self.session.execute(stmt).all()