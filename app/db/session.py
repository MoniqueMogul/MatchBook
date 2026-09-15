"""
Database session configuration for MatchBook.

Creates the SQLAlchemy engine, provides FastAPI database sessions,
and exposes a safe database connectivity check.
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://"
    "postgres:postgres@localhost:5432/matchbook"
)

DATABASE_URL = os.getenv(
    "MATCHBOOK_DATABASE_URL",
    DEFAULT_DATABASE_URL,
)


# ============================================================
# SQLALCHEMY ENGINE
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# ============================================================
# SESSION FACTORY
# ============================================================

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

def check_database_connection() -> bool:
    """
    Test whether the configured PostgreSQL database can be reached.

    Uses SELECT 1 only.

    No records are inserted, updated, or deleted.
    """

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT 1")
            )

            return (
                result.scalar_one()
                == 1
            )

    except SQLAlchemyError:
        return False


# ============================================================
# FASTAPI DATABASE DEPENDENCY
# ============================================================

def get_db() -> Generator[
    Session,
    None,
    None,
]:
    """
    Provide one SQLAlchemy session per FastAPI request.

    The session is always closed after the request completes.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()