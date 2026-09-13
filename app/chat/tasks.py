from uuid import UUID

from app.chat.repository import ChatRepository
from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.db_enum import EventConsumer, EventType
from app.events.payload_schema import NdaCompletedPayload
from app.events.repository import OutboxRepository


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def process_chat_event(
    event: dict,
) -> None:
    session = SessionLocal()

    try:
        event_id = UUID(event["event_id"])

        outbox_repository = OutboxRepository(session)
        chat_repository = ChatRepository(session)

        outbox_repository.require_event(
            event_id
        )

        if outbox_repository.is_processed(
            event_id=event_id,
            consumer=EventConsumer.CHAT,
        ):
            return

        event_type = EventType(
            event["event_type"]
        )

        if event_type == EventType.NDA_COMPLETED:
            payload = NdaCompletedPayload.model_validate(
                event["payload"]
            )

            conversation = (
                chat_repository.get_conversation_by_match(
                    payload.match_id
                )
            )

            if conversation is None:
                chat_repository.create_conversation(
                    payload.match_id
                )

        else:
            raise ValueError(
                f"Unsupported chat event: {event_type.value}"
            )

        outbox_repository.mark_processed(
            event_id=event_id,
            consumer=EventConsumer.CHAT,
        )

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()