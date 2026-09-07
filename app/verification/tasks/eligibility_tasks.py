"""Recomputes eligibility when verified funds / financing amounts change."""


def recalculate_eligibility_task(buyer_id: str, business_id: str) -> None:
    from uuid import UUID

    from app.db.database import SessionLocal

    from app.verification.services import eligibility_service

    db = SessionLocal()
    try:
        eligibility_service.calculate_eligibility(db, UUID(buyer_id), UUID(business_id))
    finally:
        db.close()