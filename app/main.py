from fastapi import FastAPI

from app.intake.routes import (
    router as intake_router,
)

from app.notification.routes import router as notification_router

app = FastAPI()

app.include_router(
    intake_router,
)
app.include_router(
    notification_router,
)