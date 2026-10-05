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
    DocumentUploadResponse, DocumentDownloadResponse,
)
from app.verification.services.documents import DocumentService


router = APIRouter(
    prefix="/documents",
    tags=["verification-documents"],
)


def _service(
    db: Session,
) -> DocumentService:
    settings = VerificationSettings.from_env()

    return DocumentService(
        db,
        R2DocumentStorage(settings),
        settings,
    )


# ============================================================
# BUYER DOCUMENTS
# ============================================================


@router.get(
    "/buyer",
    response_model=list[DocumentResponse],
)
def list_buyer_documents(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    """
    Return document metadata belonging to the authenticated buyer.

    The frontend does not supply buyer_financials_id.

    This endpoint is read-only. If the buyer has no financial
    container/documents yet, the service returns an empty list.
    """

    try:
        return _service(
            db
        ).list_buyer_documents(
            user_id
        )

    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/buyer",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def initiate_buyer_upload(
    request: DocumentUploadRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Start a buyer document upload.

    Buyer identity comes from authentication.

    BuyerProfile and BuyerFinancials resolution remain entirely
    inside the verification backend.
    """

    try:
        return _service(
            db
        ).initiate_buyer_upload(
            request,
            user_id,
        )

    except Exception as exc:
        raise _http_error(exc) from exc


# ============================================================
# BUSINESS DOCUMENTS
# ============================================================


@router.get(
    "/businesses/{business_id}",
    response_model=list[DocumentResponse],
)
def list_business_documents(
    business_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    """
    Return document metadata for one business owned by the
    authenticated seller.

    The frontend supplies the public business_id only.

    The verification backend resolves BusinessFinancials
    internally.

    This endpoint is read-only. If no BusinessFinancials record
    exists yet, the service returns an empty list.
    """

    try:
        return _service(
            db
        ).list_business_documents(
            business_id,
            user_id,
        )

    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/businesses/{business_id}",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def initiate_business_upload(
    business_id: UUID,
    request: DocumentUploadRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Start a document upload for an owned business.

    The frontend supplies the public business_id only.

    Seller ownership, BusinessFinancials resolution/creation,
    document ownership, and declaration persistence are handled
    by the verification backend.
    """

    try:
        return _service(
            db
        ).initiate_business_upload(
            business_id,
            request,
            user_id,
        )

    except Exception as exc:
        raise _http_error(exc) from exc


# ============================================================
# SHARED DOCUMENT OPERATIONS
# ============================================================

@router.get(
    "/{document_id}/download",
    response_model=DocumentDownloadResponse,
)
def download_document(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentDownloadResponse:
    try:
        return _service(
            db
        ).create_download_url(
            document_id,
            user_id,
        )

    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """
    Return metadata for a document owned by the authenticated user.

    This returns document metadata, not the stored PDF bytes.
    """

    try:
        return _service(
            db
        ).get_owned_document(
            document_id,
            user_id,
        )

    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/{document_id}/confirm",
    response_model=DocumentResponse,
)
def confirm_upload(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """
    Confirm that the client successfully uploaded the PDF to R2.

    The service verifies ownership and confirms that the R2 object
    actually exists before transitioning the document to uploaded.
    """

    try:
        return _service(
            db
        ).confirm_upload(
            document_id,
            user_id,
        )

    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/{document_id}/verify",
    response_model=DocumentResponse,
)
def trigger_verification(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """
    Explicitly trigger or retry document verification.

    Normal first-time upload processing is already dispatched by
    the confirmation flow. This endpoint remains available for
    explicit verification/retry operations.
    """

    try:
        return _service(
            db
        ).trigger_verification(
            document_id,
            user_id,
        )

    except Exception as exc:
        raise _http_error(exc) from exc


# ============================================================
# ERROR MAPPING
# ============================================================


def _http_error(
    exc: Exception,
) -> HTTPException:
    if isinstance(
        exc,
        ResourceNotFoundError,
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    if isinstance(
        exc,
        InvalidVerificationRequest,
    ):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if isinstance(
        exc,
        ProviderConfigurationError,
    ):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    if isinstance(
        exc,
        ProviderError,
    ):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Document operation failed",
    )