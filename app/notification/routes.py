from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.notification.depenencies import get_db_session
from app.notification.repository import (
    NotificationNotFoundError,
    NotificationRepository,
)
from app.notification.schema import NotificationResponse
from app.auth.dependencies import get_current_user_id


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


def get_notification_repository(
    session: Session = Depends(get_db_session),
) -> NotificationRepository:
    return NotificationRepository(
        session
    )



@router.get(
    "",
    response_model=list[NotificationResponse],
)
def list_notifications(
    current_user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
):
    repository = NotificationRepository(session)

    return repository.get_notifications(
        user_id=current_user_id,
    )


def get_notification(
    notification_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    repository: NotificationRepository = Depends(
        get_notification_repository
    ),
):
    notifications = repository.get_notification(
        notification_id=notification_id,
        user_id=current_user_id,
    )

    return notifications



@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
def mark_notification_as_read(
    notification_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
):
    repository = NotificationRepository(session)

    try:
        notification = repository.mark_notification_as_read(
            notification_id=notification_id,
            user_id=current_user_id,
        )

        session.commit()

        return notification

    except NotificationNotFoundError as exc:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    except Exception:
        session.rollback()
        raise