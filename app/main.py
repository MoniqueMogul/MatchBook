from fastapi import FastAPI

from app.auth.tests.auth_test import test_router

app = FastAPI()

app.include_router(test_router)