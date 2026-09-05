from fastapi import FastAPI

from app.matching.routes import router as matching_router


app = FastAPI(
    title="MatchBook API",
    description=(
        "Backend API for the MatchBook "
        "AI-powered business matchmaking platform."
    ),
    version="0.1.0",
)


@app.get(
    "/health",
    tags=["Health"],
)
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "matchbook-api",
    }


app.include_router(
    matching_router
)