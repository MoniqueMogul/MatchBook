from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    HTTPException,
)

from sqlalchemy import text


logger = logging.getLogger(
    "matchbook.health"
)


router = APIRouter(
    tags=[
        "Monitoring",
    ]
)


def check_database_health() -> bool:
    """
    Verify that PostgreSQL can execute a lightweight query.

    The database module is imported lazily so a database
    configuration problem does not prevent the FastAPI
    application itself from starting.
    """

    try:
        from app.db.database import (
            engine,
        )

        with engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT 1"
                )
            )

        return True

    except Exception:
        logger.exception(
            "database_health_check_failed"
        )

        return False


@router.get(
    "/health",
)
def application_health() -> dict[
    str,
    str,
]:
    """
    Basic application liveness endpoint.
    """

    return {
        "status": "healthy",
        "service": "matchbook-api",
    }


@router.get(
    "/health/database",
)
def database_health() -> dict[
    str,
    str,
]:
    """
    Database connectivity health endpoint.
    """

    if not check_database_health():
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is unavailable"
            ),
        )

    return {
        "status": "healthy",
        "service": "database",
    }