from time import monotonic, sleep
from uuid import uuid4

from app.db.database import SessionLocal
from app.db.db_enum import EventType, OutboxStatus
from app.db.db_model import User
from app.events.payload_schema import MatchCreatedPayload
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate
from app.events.tasks import retry_pending_outbox_events
from app.notification.repository import NotificationRepository


def test_pending_outbox_event_is_retried_and_processed():
    session = SessionLocal()

    user = None
    outbox_event = None
    notification = None

    try:
        user_id = uuid4()

        user = User(
            id=user_id,
            first_name="Poller",
            last_name="Test",
        )

        session.add(user)
        session.flush()

        match_id = uuid4()

        payload = MatchCreatedPayload(
            user_id=user_id,
            match_id=match_id,
        )

        event_data = OutboxEventCreate(
            idempotency_key=f"poller:test:{uuid4()}",
            event_type=EventType.MATCH_CREATED,
            entity_type="match",
            entity_id=match_id,
            payload=payload.model_dump(mode="json"),
        )

        repository = OutboxRepository(session)

        outbox_event = repository.create_event(
            event_data
        )

        # Important:
        # Do NOT call send_outbox_event here.
        # We deliberately leave this event PENDING
        # so the backup poller has to recover it.
        session.commit()

        event_id = outbox_event.id

        assert outbox_event.status == OutboxStatus.PENDING

        # Run the poller.
        retry_pending_outbox_events.delay()

        deadline = monotonic() + 20

        while monotonic() < deadline:
            session.expire_all()

            current_event = repository.require_event(
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
                current_event.status == OutboxStatus.PROCESSED
                and notification is not None
            ):
                break

            sleep(0.5)

        session.expire_all()

        current_event = repository.require_event(
            event_id
        )

        assert current_event.status == OutboxStatus.PROCESSED
        assert current_event.published_at is not None
        assert current_event.processed_at is not None
        assert notification is not None

    finally:
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
