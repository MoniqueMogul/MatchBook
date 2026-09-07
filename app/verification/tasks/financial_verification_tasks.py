"""
Financial verification: compares AI-extracted document fields against
seller-submitted Intake figures. Runs inline until Celery wiring exists.
"""


def run_financial_verification_task(business_id: str, extracted_document_fields: dict) -> None:
    from app.db.database import SessionLocal

    from app.verification.services import financial_verification_service

    db = SessionLocal()
    try:
        financial_verification_service.verify_business_financials(
            db, business_id=business_id, extracted_document_fields=extracted_document_fields
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()