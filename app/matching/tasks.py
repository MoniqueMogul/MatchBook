from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.matching.services.event_service import (
    process_matching_event_service,
)


@celery_app.task(
    name="app.matching.tasks.process_matching_event",
    autoretry_for=(
        TimeoutError,
        ConnectionError,
        SQLAlchemyError,
    ),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def process_matching_event(
    event: dict[str, Any],
) -> dict[str, Any]:

    session = SessionLocal()

    try:
        result = process_matching_event_service(
            session=session,
            event=event,
        )

        session.commit()

        return result

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()