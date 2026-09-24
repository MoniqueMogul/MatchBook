from fastapi import APIRouter

from app.verification.routes.documents import router as documents_router
from app.verification.routes.identity import router as identity_router
from app.verification.routes.plaid import router as plaid_router

router = APIRouter(prefix="/verification")
router.include_router(documents_router)
router.include_router(plaid_router)
router.include_router(identity_router)
