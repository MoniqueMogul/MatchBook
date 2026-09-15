from fastapi import FastAPI, HTTPException

from app.db.session import (
    check_database_connection,
)

from app.intake.routes import (
    router as intake_router,
)

from app.matching.routes import (
    router as matching_router,
)

from app.notification.routes import (
    router as notification_router,
)

from app.verification.routes.documents import (
    router as documents_router,
)

from app.verification.routes.eligibility import (
    router as eligibility_router,
)

from app.verification.routes.verification import (
    router as verification_router,
)

from app.core.observability import (
    RequestLogMiddleware,
    configure_logging,
)

configure_logging()

app = FastAPI(
    title="MatchBook API",
    description=(
        "Backend API for the MatchBook "
        "AI-powered business matchmaking platform."
    ),
    version="0.1.0",
)


app.add_middleware(RequestLogMiddleware)

# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    intake_router,
)

app.include_router(
    matching_router,
)

app.include_router(
    notification_router,
)

app.include_router(
    documents_router,
)

app.include_router(
    eligibility_router,
)

app.include_router(
    verification_router,
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
        "services": "matchbook-api",
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
        "services": "database",
    }