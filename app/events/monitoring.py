from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import func, select

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.db_enum import OutboxStatus
from app.db.db_model import OutboxEvent


logger = logging.getLogger("matchbook.monitoring")


@celery_app.task(ignore_result=True)
def check_outbox_backlog() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=10
    )

    with SessionLocal() as session:
        pending_count = session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PENDING
            )
        )

        old_pending_count = session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PENDING,
                OutboxEvent.created_at < cutoff,
            )
        )

        repeated_failure_count = session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PENDING,
                OutboxEvent.attempt_count >= 3,
            )
        )

    logger.info(
        "outbox_backlog",
        extra={
            "event": "outbox_backlog",
            "count": pending_count or 0,
        },
    )

    if old_pending_count or repeated_failure_count:
        logger.warning(
            "outbox_stuck",
            extra={
                "event": "outbox_stuck",
                "count": old_pending_count
                or repeated_failure_count,
            },
        )