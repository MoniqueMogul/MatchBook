from time import sleep
from uuid import uuid4

from sqlalchemy import  select

from app.chat.repository import ChatRepository
from app.db.database import SessionLocal
from app.db.db_enum import (
    BusinessType,
    BuyerType,
    EventConsumer,
    EventType,
    NotificationType,
    OutboxStatus,
)
from app.db.db_model import (
    Business,
    BuyerProfile,
    Conversation,
    Match,
    Message,
    Notification,
    OutboxEvent,
    SellerProfile,
    User,
)
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate
from app.events.tasks import send_outbox_event


def test_message_created_notifies_recipient():
    session = SessionLocal()

    buyer_user = None
    seller_user = None
    buyer_profile = None
    seller_profile = None
    business = None
    match = None
    conversation = None
    message = None
    outbox_event = None
    notification = None

    try:
        # ---------------------------------------------------------
        # 1. Create buyer + seller users
        # ---------------------------------------------------------

        buyer_user = User(
            id=uuid4(),
            first_name="Buyer",
            last_name="Message E2E",
        )

        seller_user = User(
            id=uuid4(),
            first_name="Seller",
            last_name="Message E2E",
        )

        session.add_all([
            buyer_user,
            seller_user,
        ])
        session.flush()

        # ---------------------------------------------------------
        # 2. Create buyer + seller profiles
        # ---------------------------------------------------------

        buyer_profile = BuyerProfile(
            id=uuid4(),
            user_id=buyer_user.id,
            buyer_type=BuyerType.EXISTING_BUSINESS_OWNER,
        )

        seller_profile = SellerProfile(
            id=uuid4(),
            user_id=seller_user.id,
        )

        session.add_all([
            buyer_profile,
            seller_profile,
        ])
        session.flush()

        # ---------------------------------------------------------
        # 3. Create business
        # ---------------------------------------------------------

        business = Business(
            id=uuid4(),
            seller_id=seller_profile.id,
            idempotency_key=f"e2e-business:{uuid4()}",
            business_type=BusinessType.RETAIL,
            industry="Retail",
            city="Austin",
            state="TX",
            zip_code="78701",
        )

        session.add(business)
        session.flush()

        # ---------------------------------------------------------
        # 4. Create match
        # ---------------------------------------------------------

        match = Match(
            id=uuid4(),
            buyer_id=buyer_profile.id,
            business_id=business.id,
            score=0.85,
            matching_version="v1",
        )

        session.add(match)
        session.flush()

        # ---------------------------------------------------------
        # 5. Create conversation
        # ---------------------------------------------------------

        chat_repository = ChatRepository(session)

        conversation = chat_repository.create_conversation(
            match.id
        )

        # ---------------------------------------------------------
        # 6. Buyer sends message
        # ---------------------------------------------------------

        message = chat_repository.create_message(
            conversation_id=conversation.id,
            sender_id=buyer_user.id,
            content="Hi, I'm interested in learning more about the business.",
        )

        # ---------------------------------------------------------
        # 7. Create MESSAGE_CREATED event in same transaction
        # ---------------------------------------------------------

        outbox_repository = OutboxRepository(session)

        outbox_event = outbox_repository.create_event(
            OutboxEventCreate(
                idempotency_key=f"message-created:{message.id}",
                event_type=EventType.MESSAGE_CREATED,
                entity_type="message",
                entity_id=message.id,
                payload={
                    "recipient_user_id": str(seller_user.id),
                    "conversation_id": str(conversation.id),
                    "message_id": str(message.id),
                },
            )
        )

        # Message + Outbox event commit together.
        session.commit()

        event_id = outbox_event.id
        message_id = message.id
        conversation_id = conversation.id
        seller_user_id = seller_user.id

        # ---------------------------------------------------------
        # 8. Publish event through real Celery flow
        # ---------------------------------------------------------

        send_outbox_event.delay(
            str(event_id)
        )

        # ---------------------------------------------------------
        # 9. Wait for workers to process event
        # ---------------------------------------------------------

        processed = False

        for _ in range(20):
            sleep(1)

            session.expire_all()

            if outbox_repository.is_processed(
                event_id=event_id,
                consumer=EventConsumer.NOTIFICATION,
            ):
                processed = True
                break

        assert processed is True

        # ---------------------------------------------------------
        # 10. Verify message exists
        # ---------------------------------------------------------

        saved_message = session.get(
            Message,
            message_id,
        )

        assert saved_message is not None
        assert saved_message.sender_id == buyer_user.id
        assert saved_message.conversation_id == conversation_id

        # ---------------------------------------------------------
        # 11. Verify Outbox event published
        # ---------------------------------------------------------

        current_event = session.get(
            OutboxEvent,
            event_id,
        )

        assert current_event is not None
        assert current_event.status == OutboxStatus.PUBLISHED

        assert outbox_repository.is_processed(
            event_id=event_id,
            consumer=EventConsumer.NOTIFICATION,
        )

        # ---------------------------------------------------------
        # 12. Verify seller received NEW_MESSAGE notification
        # ---------------------------------------------------------

        notification = session.scalar(
            select(Notification)
            .where(
                Notification.user_id == seller_user_id,
                Notification.type == NotificationType.NEW_MESSAGE,
            )
            .order_by(Notification.created_at.desc())
        )

        assert notification is not None
        assert notification.user_id == seller_user_id

        # Buyer should NOT receive their own NEW_MESSAGE notification.
        buyer_notification = session.scalar(
            select(Notification)
            .where(
                Notification.user_id == buyer_user.id,
                Notification.type == NotificationType.NEW_MESSAGE,
            )
        )

        assert buyer_notification is None

    finally:
        session.rollback()

        # ---------------------------------------------------------
        # Cleanup
        # ---------------------------------------------------------

        try:
            if notification is not None:
                session.delete(notification)

            if outbox_event is not None:
                event = session.get(
                    OutboxEvent,
                    outbox_event.id,
                )

                if event is not None:
                    session.delete(event)

            if message is not None:
                current_message = session.get(
                    Message,
                    message.id,
                )

                if current_message is not None:
                    session.delete(current_message)

            if conversation is not None:
                current_conversation = session.get(
                    Conversation,
                    conversation.id,
                )

                if current_conversation is not None:
                    session.delete(current_conversation)

            if match is not None:
                current_match = session.get(
                    Match,
                    match.id,
                )

                if current_match is not None:
                    session.delete(current_match)

            if business is not None:
                current_business = session.get(
                    Business,
                    business.id,
                )

                if current_business is not None:
                    session.delete(current_business)

            if seller_profile is not None:
                current_seller_profile = session.get(
                    SellerProfile,
                    seller_profile.id,
                )

                if current_seller_profile is not None:
                    session.delete(current_seller_profile)

            if buyer_profile is not None:
                current_buyer_profile = session.get(
                    BuyerProfile,
                    buyer_profile.id,
                )

                if current_buyer_profile is not None:
                    session.delete(current_buyer_profile)

            if seller_user is not None:
                current_seller = session.get(
                    User,
                    seller_user.id,
                )

                if current_seller is not None:
                    session.delete(current_seller)

            if buyer_user is not None:
                current_buyer = session.get(
                    User,
                    buyer_user.id,
                )

                if current_buyer is not None:
                    session.delete(current_buyer)

            session.commit()

        finally:
            session.close()