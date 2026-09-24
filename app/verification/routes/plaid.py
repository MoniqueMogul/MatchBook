from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id
from app.db.session import get_db
from app.verification.config import VerificationSettings
from app.verification.exceptions import (
    ProviderConfigurationError,
    ProviderError,
    ResourceNotFoundError,
)
from app.verification.integrations.plaid import PlaidClient
from app.verification.schemas import (
    PlaidFundsResponse,
    PlaidLinkTokenResponse,
    PlaidPublicTokenRequest,
    VerificationStatusResponse,
)
from app.verification.services.plaid import PlaidService

router = APIRouter(prefix="/plaid", tags=["verification-plaid"])


def _service(db: Session) -> PlaidService:
    return PlaidService(db, PlaidClient(VerificationSettings.from_env()))


@router.post(
    "/buyer-financials/{financials_id}/link-token",
    response_model=PlaidLinkTokenResponse,
)
async def create_link_token(
    financials_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PlaidLinkTokenResponse:
    try:
        return await _service(db).create_link_token(financials_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/buyer-financials/{financials_id}/status",
    response_model=VerificationStatusResponse,
)
def get_plaid_status(
    financials_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> VerificationStatusResponse:
    try:
        return _service(db).get_status(financials_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/buyer-financials/{financials_id}/verify-funds",
    response_model=PlaidFundsResponse,
)
async def verify_funds(
    financials_id: UUID,
    request: PlaidPublicTokenRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PlaidFundsResponse:
    try:
        return await _service(db).verify_funds(
            financials_id,
            user_id,
            request.public_token,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ResourceNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ProviderConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ProviderError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail="Plaid verification failed")
