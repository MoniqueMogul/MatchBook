from uuid import uuid4

from app.db.db_enum import NotificationType
from app.db.db_model import User
from app.notification.repository import NotificationRepository
from app.notification.schema import NotificationCreate


def test_create_notification_in_database(db_session):
    user_id = uuid4()

    user = User(
        id=user_id,
        first_name="Test",
        last_name="User",
    )

    db_session.add(user)
    db_session.flush()

    repository = NotificationRepository(db_session)

    data = NotificationCreate(
        type=NotificationType.NEW_MATCH,
        title="New match available",
        message="A new business match is available for you.",
        related_entity_type="match",
        related_entity_id=uuid4(),
    )

    notification = repository.create_notification(
        user_id=user_id,
        data=data,
    )

    db_session.flush()

    assert notification.id is not None
    assert notification.user_id == user_id
    assert notification.type == NotificationType.NEW_MATCH
    assert notification.title == "New match available"
    assert notification.read_at is None