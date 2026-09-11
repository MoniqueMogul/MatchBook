from time import monotonic, sleep
from uuid import uuid4

from app.db.database import SessionLocal
from app.db.db_enum import (
    EventType,
    NotificationType,
    OutboxStatus,
)
from app.db.db_model import User
from app.events.payload_schema import MatchCreatedPayload
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate
from app.events.tasks import send_outbox_event
from app.notification.repository import NotificationRepository


def test_outbox_to_notification_e2e():
    session = SessionLocal()

    user = None
    outbox_event = None
    notification = None

    try:
        # 1. Create a real test user.
        user_id = uuid4()

        user = User(
            id=user_id,
            first_name="E2E",
            last_name="Test",
        )

        session.add(user)
        session.flush()

        # 2. Build a real MATCH_CREATED event.
        match_id = uuid4()

        payload = MatchCreatedPayload(
            user_id=user_id,
            match_id=match_id,
        )

        event_data = OutboxEventCreate(
            idempotency_key=f"e2e:match-created:{uuid4()}",
            event_type=EventType.MATCH_CREATED,
            entity_type="match",
            entity_id=match_id,
            payload=payload.model_dump(mode="json"),
        )

        outbox_repository = OutboxRepository(session)

        outbox_event = outbox_repository.create_event(
            event_data
        )

        # Important:
        # Worker runs in another process/session,
        # so it must be committed first.
        session.commit()

        event_id = outbox_event.id

        # 3. Send the real task through RabbitMQ.
        send_outbox_event.delay(
            str(event_id)
        )

        # 4. Poll DB until Celery finishes processing.
        deadline = monotonic() + 20

        while monotonic() < deadline:
            session.expire_all()

            current_event = outbox_repository.require_event(
                event_id
            )

            notification_repository = NotificationRepository(
                session
            )

            notifications = (
                notification_repository.get_notifications(
                    user_id=user_id
                )
            )

            notification = next(
                (
                    item
                    for item in notifications
                    if item.related_entity_id == match_id
                ),
                None,
            )

            if (
                current_event.status
                == OutboxStatus.PROCESSED
                and notification is not None
            ):
                break

            sleep(0.5)

        # 5. Verify final Outbox state.
        session.expire_all()

        current_event = outbox_repository.require_event(
            event_id
        )

        assert current_event.status == OutboxStatus.PROCESSED
        assert current_event.published_at is not None
        assert current_event.processed_at is not None

        # 6. Verify notification was really persisted.
        assert notification is not None
        assert notification.user_id == user_id
        assert notification.type == NotificationType.NEW_MATCH
        assert notification.related_entity_type == "match"
        assert notification.related_entity_id == match_id

    finally:
        # These records were committed because Celery needs
        # to see them, so clean them up explicitly.
        session.rollback()

        if notification is not None:
            notification = session.merge(notification)
            session.delete(notification)

        if outbox_event is not None:
            outbox_event = session.merge(outbox_event)
            session.delete(outbox_event)

        if user is not None:
            user = session.merge(user)
            session.delete(user)

        session.commit()
        session.close()