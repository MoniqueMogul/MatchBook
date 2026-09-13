from time import monotonic, sleep
from uuid import uuid4

from app.chat.repository import ChatRepository
from app.db.database import SessionLocal
from app.db.db_enum import (
    EventConsumer,
    EventType,
    OutboxStatus, BusinessType,
)
from app.db.db_model import (
    Business,
    BuyerProfile,
    Match,
    SellerProfile,
    User,
)
from app.events.payload_schema import NdaCompletedPayload
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate
from app.events.tasks import send_outbox_event
from app.notification.repository import NotificationRepository
from app.db.db_enum import BuyerType

def test_nda_completed_creates_notification_and_conversation():
    session = SessionLocal()

    buyer_user = None
    seller_user = None
    buyer_profile = None
    seller_profile = None
    business = None
    match = None
    outbox_event = None
    notification = None
    conversation = None

    try:
        # 1. Create buyer + seller users.
        buyer_user = User(
            id=uuid4(),
            first_name="Buyer",
            last_name="E2E",
        )

        seller_user = User(
            id=uuid4(),
            first_name="Seller",
            last_name="E2E",
        )

        session.add_all([
            buyer_user,
            seller_user,
        ])
        session.flush()

        # 2. Create buyer and seller profiles.


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

        # 3. Create business.
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

        # 4. Create match.
        match = Match(
            id=uuid4(),
            buyer_id=buyer_profile.id,
            business_id=business.id,
            score=0.85,
            matching_version="v1",
        )

        session.add(match)
        session.flush()

        # 5. Build NDA_COMPLETED event.
        nda_id = uuid4()

        payload = NdaCompletedPayload(
            user_id=buyer_user.id,
            nda_id=nda_id,
            match_id=match.id,
        )

        outbox_repository = OutboxRepository(
            session
        )

        outbox_event = outbox_repository.create_event(
            OutboxEventCreate(
                idempotency_key=f"e2e:nda-completed:{uuid4()}",
                event_type=EventType.NDA_COMPLETED,
                entity_type="nda",
                entity_id=nda_id,
                payload=payload.model_dump(
                    mode="json"
                ),
            )
        )

        # Worker uses another DB session.
        session.commit()

        event_id = outbox_event.id

        # 6. Publish through real RabbitMQ/Celery flow.
        send_outbox_event.delay(
            str(event_id)
        )

        # 7. Wait for both consumers.
        deadline = monotonic() + 20

        while monotonic() < deadline:
            session.expire_all()

            current_event = (
                outbox_repository.require_event(
                    event_id
                )
            )

            notification_repository = (
                NotificationRepository(
                    session
                )
            )

            notifications = (
                notification_repository
                .get_notifications(
                    user_id=buyer_user.id
                )
            )

            notification = next(
                (
                    item
                    for item in notifications
                    if item.related_entity_id == nda_id
                ),
                None,
            )

            chat_repository = ChatRepository(
                session
            )

            conversation = (
                chat_repository
                .get_conversation_by_match(
                    match.id
                )
            )

            notification_processed = (
                outbox_repository.is_processed(
                    event_id=event_id,
                    consumer=EventConsumer.NOTIFICATION,
                )
            )

            chat_processed = (
                outbox_repository.is_processed(
                    event_id=event_id,
                    consumer=EventConsumer.CHAT,
                )
            )

            if (
                current_event.status
                == OutboxStatus.PUBLISHED
                and notification is not None
                and conversation is not None
                and notification_processed
                and chat_processed
            ):
                break

            sleep(0.5)

        # 8. Verify Outbox was published.
        session.expire_all()

        current_event = (
            outbox_repository.require_event(
                event_id
            )
        )

        assert (
            current_event.status
            == OutboxStatus.PUBLISHED
        )

        assert (
            current_event.published_at
            is not None
        )

        # 9. Verify Notification consumer processed it.
        assert outbox_repository.is_processed(
            event_id=event_id,
            consumer=EventConsumer.NOTIFICATION,
        )

        assert notification is not None

        # 10. Verify Chat consumer processed it.
        assert outbox_repository.is_processed(
            event_id=event_id,
            consumer=EventConsumer.CHAT,
        )

        assert conversation is not None
        assert conversation.match_id == match.id

        # 11. Verify only one conversation exists.
        chat_repository = ChatRepository(
            session
        )

        same_conversation = (
            chat_repository
            .get_conversation_by_match(
                match.id
            )
        )

        assert same_conversation is not None
        assert same_conversation.id == conversation.id

    finally:
        session.rollback()

        # Delete conversation first because it references Match.
        if conversation is not None:
            current = session.get(
                type(conversation),
                conversation.id,
            )

            if current is not None:
                session.delete(current)

        # Deleting OutboxEvent also deletes its ProcessedEvent rows
        # through ON DELETE CASCADE.
        if outbox_event is not None:
            current = session.get(
                type(outbox_event),
                outbox_event.id,
            )

            if current is not None:
                session.delete(current)

        if match is not None:
            current = session.get(
                type(match),
                match.id,
            )

            if current is not None:
                session.delete(current)

        if business is not None:
            current = session.get(
                type(business),
                business.id,
            )

            if current is not None:
                session.delete(current)

        if seller_profile is not None:
            current = session.get(
                type(seller_profile),
                seller_profile.id,
            )

            if current is not None:
                session.delete(current)

        if buyer_profile is not None:
            current = session.get(
                type(buyer_profile),
                buyer_profile.id,
            )

            if current is not None:
                session.delete(current)

        if seller_user is not None:
            current = session.get(
                type(seller_user),
                seller_user.id,
            )

            if current is not None:
                session.delete(current)

        if buyer_user is not None:
            current = session.get(
                type(buyer_user),
                buyer_user.id,
            )

            if current is not None:
                session.delete(current)

        session.commit()
        session.close()