"""Recomputes eligibility when verified funds / financing amounts change."""

from uuid import UUID

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.verification.services import eligibility_service


@celery_app.task(name="app.verification.tasks.eligibility_tasks.recalculate_eligibility_task")
def recalculate_eligibility_task(buyer_id: str, business_id: str) -> None:
    db = SessionLocal()
    try:
        eligibility_service.calculate_eligibility(db, UUID(buyer_id), UUID(business_id))
    finally:
        db.close()