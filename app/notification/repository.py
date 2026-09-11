from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.db_model import Notification
from app.notification.schema import NotificationCreate


class NotificationRepositoryError(Exception):
    """
    Base exception for Notification repository errors.
    """


class NotificationNotFoundError(NotificationRepositoryError):
    """
    Raised when a notification cannot be found
    for the requested user.
    """


class NotificationRepository:
    """
    Repository responsible for Notification persistence.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def get_notifications(
        self,
        user_id: UUID,
    ) -> list[Notification]:
        """
        Load all notifications belonging to one user.

        Notifications are returned newest first.
        """

        statement = (
            select(
                Notification
            )
            .where(
                Notification.user_id
                == user_id
            )
            .order_by(
                Notification.created_at.desc()
            )
        )

        result = self.session.scalars(
            statement
        )

        return list(
            result.all()
        )

    def get_notification(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> Notification:
        """
        Load one notification belonging to one user.

        The user_id condition ensures that a user
        cannot access another user's notification.
        """

        statement = (
            select(
                Notification
            )
            .where(
                Notification.id
                == notification_id,

                Notification.user_id
                == user_id,
            )
        )

        notification = self.session.scalar(
            statement
        )

        if notification is None:
            raise NotificationNotFoundError(
                "No Notification found "
                f"for notification_id={notification_id}"
            )

        return notification

    def create_notification(
            self,
            *,
            user_id: UUID,
            data: NotificationCreate,
    ) -> Notification:
        """
        Create one notification.

        This method deliberately does NOT commit.
        Transaction ownership stays with the caller.
        """

        notification = Notification(
            user_id=user_id,
            **data.model_dump(),
        )

        self.session.add(notification)
        self.session.flush()

        return notification

    def mark_notification_as_read(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> Notification:
        """
        Mark one user's notification as read.

        If the notification is already read, its original
        read_at timestamp is preserved.
        """

        notification = self.get_notification(
            notification_id,
            user_id,
        )

        if notification.read_at is None:
            notification.read_at = datetime.now(
                timezone.utc
            )

            self.session.flush()

        return notification


