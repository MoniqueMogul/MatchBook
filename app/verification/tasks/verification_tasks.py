"""
KYC / EIN verification entry points.

Celery tasks share the worker infrastructure from app.core.celery_app.
"""

import asyncio

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.verification.services import verification_service


@celery_app.task(name="app.verification.tasks.verification_tasks.start_user_kyc_task")
def start_user_kyc_task(user_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(verification_service.start_user_kyc(db, user_id))
    finally:
        db.close()


@celery_app.task(name="app.verification.tasks.verification_tasks.start_business_verification_task")
def start_business_verification_task(business_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(verification_service.start_business_existence_check(db, business_id))
    finally:
        db.close()