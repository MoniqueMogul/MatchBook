from collections.abc import Generator

from app.intake.repository import IntakeRepository

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.intake.service import IntakeService

def get_db_session() -> Generator[
    Session,
    None,
    None,
]:
    """
    Request-scoped SQLAlchemy session.

    Import SessionLocal lazily so importing the
    Intake router does not require DATABASE_URL.
    """

    from app.db.database import SessionLocal

    session = SessionLocal()

    try:
        yield session

    finally:
        session.close()


def get_intake_repository(
    session: Session = Depends(
        get_db_session
    ),
) -> IntakeRepository:

    return IntakeRepository(
        session
    )


def get_intake_service(
    session: Session = Depends(get_db),
) -> IntakeService:

    return IntakeService(
        session
    )