import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id
from app.db.session import get_db
from app.verification.config import VerificationSettings
from app.verification.exceptions import (
    InvalidVerificationRequest,
    ProviderConfigurationError,
    ProviderError,
    ResourceNotFoundError,
)
from app.verification.integrations.didit import DiditClient
from app.verification.schemas import ProviderSession, VerificationStatusResponse
from app.verification.services.identity import IdentityService

router = APIRouter(prefix="/identity", tags=["verification-identity"])


def _components(db: Session) -> tuple[DiditClient, IdentityService]:
    provider = DiditClient(VerificationSettings.from_env())
    return provider, IdentityService(db, provider)


@router.post("/kyc/session", response_model=ProviderSession)
async def start_kyc(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProviderSession:
    try:
        _, service = _components(db)
        return await service.start_user_kyc(user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/kyc/status", response_model=VerificationStatusResponse)
def get_kyc_status(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> VerificationStatusResponse:
    try:
        _, service = _components(db)
        return service.get_user_kyc_status(user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/businesses/{business_id}/ein/session", response_model=ProviderSession)
async def start_ein(
    business_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProviderSession:
    try:
        _, service = _components(db)
        return await service.start_ein_check(business_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/businesses/{business_id}/ein/status",
    response_model=VerificationStatusResponse,
)
def get_ein_status(
    business_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> VerificationStatusResponse:
    try:
        _, service = _components(db)
        return service.get_ein_status(business_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/businesses/{business_id}/kyb/session", response_model=ProviderSession)
async def start_kyb(
    business_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProviderSession:
    try:
        _, service = _components(db)
        return await service.start_kyb(business_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/businesses/{business_id}/kyb/status",
    response_model=VerificationStatusResponse,
)
def get_kyb_status(
    business_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> VerificationStatusResponse:
    try:
        _, service = _components(db)
        return service.get_kyb_status(business_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/webhooks/didit")
async def didit_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed webhook payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Malformed webhook payload")
    provider, service = _components(db)
    signature = request.headers.get("X-Signature-V2", "")
    timestamp = request.headers.get("X-Timestamp")
    if not provider.verify_webhook(payload, signature, timestamp):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        service.apply_result(provider.parse_webhook(payload))
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"received": True}


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ResourceNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, InvalidVerificationRequest):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ProviderConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ProviderError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="Identity verification failed")
