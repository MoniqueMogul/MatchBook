from __future__ import annotations

from uuid import UUID

from app.db.db_enum import EventType, NotificationType
from app.notification.repository import NotificationRepository
from app.notification.schema import NotificationCreate


class UnsupportedNotificationEventError(Exception):
    pass



def handle_notification_event(
    *,
    event: dict,
    repository: NotificationRepository,
) -> None:
    """
    Convert a domain event into a user-facing notification.

    This function decides:
    - whether the event should create a notification
    - who should receive it
    - what notification type/title/message to use

    It does NOT commit.
    """

    event_type = EventType(
        event["event_type"]
    )

    payload = event["payload"]

    if event_type == EventType.MATCH_CREATED:
        _handle_match_created(
            payload=payload,
            repository=repository,
        )
        return

    if event_type == EventType.MATCH_STATUS_CHANGED:
        _handle_match_status_changed(
            payload=payload,
            repository=repository,
        )
        return

    if event_type == EventType.VERIFICATION_COMPLETED:
        _handle_verification_completed(
            payload=payload,
            repository=repository,
        )
        return

    if event_type == EventType.NDA_COMPLETED:
        _handle_nda_completed(
            payload=payload,
            repository=repository,
        )
        return

    if event_type == EventType.DOCUMENT_UPLOADED:
        _handle_document_uploaded(
            payload=payload,
            repository=repository,
        )
        return

    if event_type == EventType.MESSAGE_CREATED:
        _handle_message_created(
            payload=payload,
            repository=repository,
        )
        return

    raise UnsupportedNotificationEventError(
        f"Unsupported notification event: {event_type.value}"
    )


def _handle_match_created(
    *,
    payload: dict,
    repository: NotificationRepository,
) -> None:

    user_id = UUID(
        payload["user_id"]
    )

    match_id = UUID(
        payload["match_id"]
    )

    data = NotificationCreate(
        type=NotificationType.NEW_MATCH,
        title="New match available",
        message="A new business match is available for you.",
        related_entity_type="match",
        related_entity_id=match_id,
    )

    repository.create_notification(
        user_id=user_id,
        data=data,
    )


def _handle_match_status_changed(
    *,
    payload: dict,
    repository: NotificationRepository,
) -> None:

    user_id = UUID(payload["user_id"])
    match_id = UUID(payload["match_id"])
    status = payload["status"]

    data = NotificationCreate(
        type=NotificationType.MATCH_STATUS_CHANGED,
        title="Match status updated",
        message=f"Your match status changed to {status}.",
        related_entity_type="match",
        related_entity_id=match_id,
    )

    repository.create_notification(
        user_id=user_id,
        data=data,
    )


def _handle_verification_completed(
    *,
    payload: dict,
    repository: NotificationRepository,
) -> None:

    user_id = UUID(payload["user_id"])
    verification_id = UUID(payload["verification_id"])

    data = NotificationCreate(
        type=NotificationType.VERIFICATION_COMPLETED,
        title="Verification completed",
        message="Your verification has been completed.",
        related_entity_type="verification",
        related_entity_id=verification_id,
    )

    repository.create_notification(
        user_id=user_id,
        data=data,
    )


def _handle_nda_completed(
    *,
    payload: dict,
    repository: NotificationRepository,
) -> None:

    user_id = UUID(payload["user_id"])
    nda_id = UUID(payload["nda_id"])

    data = NotificationCreate(
        type=NotificationType.NDA_COMPLETED,
        title="NDA completed",
        message="The NDA process has been completed.",
        related_entity_type="nda",
        related_entity_id=nda_id,
    )

    repository.create_notification(
        user_id=user_id,
        data=data,
    )


def _handle_document_uploaded(
    *,
    payload: dict,
    repository: NotificationRepository,
) -> None:

    user_id = UUID(payload["user_id"])
    document_id = UUID(payload["document_id"])

    data = NotificationCreate(
        type=NotificationType.DOCUMENT_UPLOADED,
        title="New document available",
        message="A new document has been uploaded.",
        related_entity_type="document",
        related_entity_id=document_id,
    )

    repository.create_notification(
        user_id=user_id,
        data=data,
    )


def _handle_message_created(
    *,
    payload: dict,
    repository: NotificationRepository,
) -> None:

    recipient_user_id = UUID(
        payload["recipient_user_id"]
    )

    conversation_id = UUID(
        payload["conversation_id"]
    )

    data = NotificationCreate(
        type=NotificationType.NEW_MESSAGE,
        title="New message",
        message="You received a new message.",
        related_entity_type="conversation",
        related_entity_id=conversation_id,
    )

    repository.create_notification(
        user_id=recipient_user_id,
        data=data,
    )