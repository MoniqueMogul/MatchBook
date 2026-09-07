from fastapi import FastAPI

from app.intake.routes import router as intake_router
from app.verification.routes.documents import router as documents_router
from app.verification.routes.eligibility import router as eligibility_router
from app.verification.routes.verification import router as verification_router

app = FastAPI(title="MatchBook API")

app.include_router(intake_router)
app.include_router(verification_router)
app.include_router(documents_router)
app.include_router(eligibility_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}