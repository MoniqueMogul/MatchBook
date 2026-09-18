# app/chat/routes.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id
from app.chat.repository import (
    ConversationNotFoundError,
    MessageNotFoundError,
)
from app.chat.schema import (
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)
from app.chat.service import (
    ChatAccessDeniedError,
    ChatService,
    MessageReadForbiddenError,
)
from app.events.tasks import send_outbox_event
from app.notification.depenencies import get_db_session

from app.chat.ai_chat_assistant.route import (
    router as ai_chat_assistant_router,
)


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)

router.include_router(
    ai_chat_assistant_router,
)

@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
)
def list_conversations(
    current_user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
):
    service = ChatService(session)

    return service.list_conversations(
        user_id=current_user_id,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def get_messages(
    conversation_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
):
    service = ChatService(session)

    try:
        return service.get_messages(
            conversation_id=conversation_id,
            user_id=current_user_id,
        )

    except (
        ConversationNotFoundError,
        ChatAccessDeniedError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )



@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    current_user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
):
    service = ChatService(session)

    try:
        message, outbox_event = service.send_message(
            conversation_id=conversation_id,
            user_id=current_user_id,
            data=data,
        )

        session.commit()

        send_outbox_event.delay(
            str(outbox_event.id)
        )

        return message

    except (
        ConversationNotFoundError,
        ChatAccessDeniedError,
    ) as exc:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    except Exception:
        session.rollback()
        raise



@router.patch(
    "/messages/{message_id}/read",
    response_model=MessageResponse,
)
def mark_message_as_read(
    message_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
):
    service = ChatService(session)

    try:
        message = service.mark_message_as_read(
            message_id=message_id,
            user_id=current_user_id,
        )

        session.commit()

        return message

    except (
        MessageNotFoundError,
        ChatAccessDeniedError,
    ) as exc:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    except MessageReadForbiddenError as exc:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    except Exception:
        session.rollback()
        raise