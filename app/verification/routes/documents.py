from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.verification.integrations.storage import R2DocumentStorage
from app.verification.schemas import (
    DocumentResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
)
from app.verification.services.documents import DocumentService

router = APIRouter(prefix="/documents", tags=["verification-documents"])


def _service(db: Session) -> DocumentService:
    settings = VerificationSettings.from_env()
    return DocumentService(db, R2DocumentStorage(settings), settings)


@router.post("", response_model=DocumentUploadResponse, status_code=201)
def initiate_upload(
    request: DocumentUploadRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    try:
        return _service(db).initiate_upload(request, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/{document_id}/confirm", response_model=DocumentResponse)
def confirm_upload(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        return _service(db).confirm_upload(document_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/{document_id}/verify", response_model=DocumentResponse)
def trigger_verification(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        return _service(db).trigger_verification(document_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        return _service(db).get_owned_document(document_id, user_id)
    except Exception as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ResourceNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, InvalidVerificationRequest):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ProviderConfigurationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    if isinstance(exc, ProviderError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail="Document operation failed")
