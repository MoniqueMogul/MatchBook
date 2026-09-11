from __future__ import annotations

from app.db.db_enum import EventType, NotificationType
from app.events.payload_schema import (
    DocumentUploadedPayload,
    MatchCreatedPayload,
    MatchStatusChangedPayload,
    MessageCreatedPayload,
    NdaCompletedPayload,
    VerificationCompletedPayload,
)
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

    The payload is validated against the schema for that
    specific event type before being processed.

    This function does NOT commit.
    """

    event_type = EventType(
        event["event_type"]
    )

    payload = event["payload"]

    if event_type == EventType.MATCH_CREATED:
        _handle_match_created(
            payload=MatchCreatedPayload.model_validate(payload),
            repository=repository,
        )
        return

    if event_type == EventType.MATCH_STATUS_CHANGED:
        _handle_match_status_changed(
            payload=MatchStatusChangedPayload.model_validate(payload),
            repository=repository,
        )
        return

    if event_type == EventType.VERIFICATION_COMPLETED:
        _handle_verification_completed(
            payload=VerificationCompletedPayload.model_validate(payload),
            repository=repository,
        )
        return

    if event_type == EventType.NDA_COMPLETED:
        _handle_nda_completed(
            payload=NdaCompletedPayload.model_validate(payload),
            repository=repository,
        )
        return

    if event_type == EventType.DOCUMENT_UPLOADED:
        _handle_document_uploaded(
            payload=DocumentUploadedPayload.model_validate(payload),
            repository=repository,
        )
        return

    if event_type == EventType.MESSAGE_CREATED:
        _handle_message_created(
            payload=MessageCreatedPayload.model_validate(payload),
            repository=repository,
        )
        return

    raise UnsupportedNotificationEventError(
        f"Unsupported notification event: {event_type.value}"
    )


def _handle_match_created(
    *,
    payload: MatchCreatedPayload,
    repository: NotificationRepository,
) -> None:

    data = NotificationCreate(
        type=NotificationType.NEW_MATCH,
        title="New match available",
        message="A new business match is available for you.",
        related_entity_type="match",
        related_entity_id=payload.match_id,
    )

    repository.create_notification(
        user_id=payload.user_id,
        data=data,
    )


def _handle_match_status_changed(
    *,
    payload: MatchStatusChangedPayload,
    repository: NotificationRepository,
) -> None:

    data = NotificationCreate(
        type=NotificationType.MATCH_STATUS_CHANGED,
        title="Match status updated",
        message=f"Your match status changed to {payload.status}.",
        related_entity_type="match",
        related_entity_id=payload.match_id,
    )

    repository.create_notification(
        user_id=payload.user_id,
        data=data,
    )


def _handle_verification_completed(
    *,
    payload: VerificationCompletedPayload,
    repository: NotificationRepository,
) -> None:

    data = NotificationCreate(
        type=NotificationType.VERIFICATION_COMPLETED,
        title="Verification completed",
        message="Your verification has been completed.",
        related_entity_type="verification",
        related_entity_id=payload.verification_id,
    )

    repository.create_notification(
        user_id=payload.user_id,
        data=data,
    )


def _handle_nda_completed(
    *,
    payload: NdaCompletedPayload,
    repository: NotificationRepository,
) -> None:

    data = NotificationCreate(
        type=NotificationType.NDA_COMPLETED,
        title="NDA completed",
        message="The NDA process has been completed.",
        related_entity_type="nda",
        related_entity_id=payload.nda_id,
    )

    repository.create_notification(
        user_id=payload.user_id,
        data=data,
    )


def _handle_document_uploaded(
    *,
    payload: DocumentUploadedPayload,
    repository: NotificationRepository,
) -> None:

    data = NotificationCreate(
        type=NotificationType.DOCUMENT_UPLOADED,
        title="New document available",
        message="A new document has been uploaded.",
        related_entity_type="document",
        related_entity_id=payload.document_id,
    )

    repository.create_notification(
        user_id=payload.user_id,
        data=data,
    )


def _handle_message_created(
    *,
    payload: MessageCreatedPayload,
    repository: NotificationRepository,
) -> None:

    data = NotificationCreate(
        type=NotificationType.NEW_MESSAGE,
        title="New message",
        message="You received a new message.",
        related_entity_type="conversation",
        related_entity_id=payload.conversation_id,
    )

    repository.create_notification(
        user_id=payload.recipient_user_id,
        data=data,
    )