from uuid import UUID

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.matching.event_service import process_matching_event


@celery_app.task
def process_matching_event_task(
    event_id: str,
) -> None:
    """
    Process one Matching outbox event.

    The task owns the database transaction.
    """

    session = SessionLocal()

    try:
        process_matching_event(
            session=session,
            event_id=UUID(event_id),
        )

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()