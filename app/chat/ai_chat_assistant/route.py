from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id
from app.chat.ai_chat_assistant.llm import AIIntroductionGenerationError
from app.chat.ai_chat_assistant.repository import AIChatContextNotFoundError
from app.chat.ai_chat_assistant.schema import (
    AIIntroductionRequest,
    AIIntroductionResponse,
)
from app.chat.ai_chat_assistant.service import AIAssistedChatService
from app.db.session import get_db


router = APIRouter(
    prefix="/conversations",
    tags=["AI Chat Assistant"],
)


@router.post(
    "/{conversation_id}/ai-suggestion",
    response_model=AIIntroductionResponse,
    status_code=status.HTTP_200_OK,
)
def generate_ai_suggestion(
    conversation_id: UUID,
    request: AIIntroductionRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: Session = Depends(get_db),
) -> AIIntroductionResponse:
    """
    Generate an AI-assisted introduction draft.

    The draft is persisted for AI observability but is not
    sent as a chat message.

    The user must explicitly send the message through the
    normal chat message endpoint.
    """

    service = AIAssistedChatService(
        session
    )

    try:
        result = service.generate_introduction(
            conversation_id=conversation_id,
            user_id=user_id,
            request=request,
        )

        # Successful generation records were only flushed
        # by the repository. Finalize them here.
        session.commit()

        return result

    except AIChatContextNotFoundError:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation context was not found.",
        )

    except PermissionError:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this conversation.",
        )

    except AIIntroductionGenerationError:
        # DO NOT rollback here.
        #
        # The service already committed the failed
        # AIChatGeneration observability record before
        # raising this exception.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to generate a suggestion right now.",
        )