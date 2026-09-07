"""
KYC / EIN verification entry points.

Celery is owned by the core/workers team; these currently run inside the
request until wiring exists.
"""


def start_user_kyc_task(user_id: str) -> None:
    from app.db.database import SessionLocal

    from app.verification.services import verification_service

    import asyncio

    db = SessionLocal()
    try:
        asyncio.run(verification_service.start_user_kyc(db, user_id))
    finally:
        db.close()


def start_business_verification_task(business_id: str) -> None:
    from app.db.database import SessionLocal

    from app.verification.services import verification_service

    import asyncio

    db = SessionLocal()
    try:
        asyncio.run(verification_service.start_business_existence_check(db, business_id))
    finally:
        db.close()