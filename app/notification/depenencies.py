from typing import Generator

from sqlalchemy.orm import Session
from app.db.database import SessionLocal

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

    session = SessionLocal()

    try:
        yield session

    finally:
        session.rollback()
        session.close()