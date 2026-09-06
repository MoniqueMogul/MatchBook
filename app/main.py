from fastapi import FastAPI, HTTPException

from app.db.session import (
    check_database_connection,
)

from app.matching.routes import (
    router as matching_router,
)


app = FastAPI(
    title="MatchBook API",
    description=(
        "Backend API for the MatchBook "
        "AI-powered business matchmaking platform."
    ),
    version="0.1.0",
)


# ============================================================
# APPLICATION HEALTH
# ============================================================


@app.get(
    "/health",
    tags=["Health"],
)
def health_check() -> dict[str, str]:
    """
    Verify that the MatchBook FastAPI application is running.
    """

    return {
        "status": "healthy",
        "service": "matchbook-api",
    }


# ============================================================
# DATABASE HEALTH
# ============================================================


@app.get(
    "/health/database",
    tags=["Health"],
)
def database_health_check() -> dict[str, str]:
    """
    Verify connectivity between the MatchBook backend
    and the configured PostgreSQL / Supabase database.

    This executes SELECT 1 only and does not modify data.
    """

    if not check_database_connection():
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )

    return {
        "status": "healthy",
        "service": "database",
    }


# ============================================================
# MATCHING ROUTER
# ============================================================


app.include_router(
    matching_router
)