import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL = os.getenv(
    "MATCHBOOK_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/matchbook",
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db():
    """
    FastAPI database-session dependency.
    """
    db: Session = SessionLocal()

    try:
        yield db

    finally:
        db.close()