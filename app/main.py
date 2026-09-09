from fastapi import FastAPI

from app.intake.routes import (
    router as intake_router,
)


app = FastAPI()

app.include_router(
    intake_router
)