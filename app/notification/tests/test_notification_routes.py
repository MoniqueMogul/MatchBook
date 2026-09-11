
from fastapi.testclient import TestClient

from app.main import app
from app.notification.depenencies import get_db_session

client = TestClient(app)


from uuid import uuid4

from app.auth.dependencies import get_current_user_id
from app.db.db_model import User
from app.notification.repository import NotificationRepository
from app.notification.schema import NotificationCreate
from app.db.db_enum import NotificationType


def test_mark_notification_as_read(db_session):
    user_id = uuid4()

    user = User(
        id=user_id,
        first_name="Test",
        last_name="User",
    )

    db_session.add(user)
    db_session.flush()

    repository = NotificationRepository(db_session)

    notification = repository.create_notification(
        user_id=user_id,
        data=NotificationCreate(
            type=NotificationType.NEW_MATCH,
            title="New match",
            message="A new match is available.",
            related_entity_type="match",
            related_entity_id=uuid4(),
        ),
    )

    db_session.flush()

    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_db_session] = lambda: db_session

    try:
        response = client.patch(
            f"/notifications/{notification.id}/read"
        )

        assert response.status_code == 200
        assert response.json()["read_at"] is not None

    finally:
        app.dependency_overrides.clear()