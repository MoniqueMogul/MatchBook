import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv

load_dotenv()

MATCHBOOK_DATABASE_URL = os.getenv("MATCHBOOK_DATABASE_URL")

if not MATCHBOOK_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set"
    )

engine = create_engine(
    MATCHBOOK_DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
