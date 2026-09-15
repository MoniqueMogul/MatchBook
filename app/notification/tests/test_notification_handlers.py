# tests/test_notification_handlers.py

from uuid import uuid4

from app.db.db_enum import EventType, NotificationType
from app.db.db_model import User
from app.notification.handlers import handle_notification_event
from app.notification.repository import NotificationRepository


from unittest.mock import Mock
from uuid import uuid4

from app.db.db_enum import EventType, NotificationType
from app.notification.handlers import handle_notification_event


def test_match_created_creates_notification():
    repository = Mock()

    user_id = uuid4()
    match_id = uuid4()

    event = {
        "event_type": EventType.MATCH_CREATED.value,
        "payload": {
            "user_id": str(user_id),
            "match_id": str(match_id),
        },
    }

    handle_notification_event(
        event=event,
        repository=repository,
    )

    repository.create_notification.assert_called_once()

    call = repository.create_notification.call_args

    assert call.kwargs["user_id"] == user_id

    notification = call.kwargs["data"]

    assert notification.type == NotificationType.NEW_MATCH
    assert notification.related_entity_id == match_id