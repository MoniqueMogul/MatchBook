from app.nda.schema import (
    NDASigningSessionResponse,
)

from app.nda.signing.factory import (
    build_signature_provider,
)

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_user_id

from app.nda.service import (
    NDAService,
    NDANotFoundError,
    NDAAccessDeniedError,
    NDAAlreadySignedError,
    NDAAlreadyCompletedError, NDASigningInitializationInProgressError,
)

from app.nda.signing.exceptions import (
    SignatureProviderError,
)


router = APIRouter(
    prefix="/nda",
    tags=["NDA"],
)


@router.post(
    "/{nda_id}/signing-session",
    response_model=NDASigningSessionResponse,
)
async def create_nda_signing_session(
    nda_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
) -> NDASigningSessionResponse:

    provider = build_signature_provider()

    service = NDAService(
        db=db,
        signature_provider=provider,
    )

    try:
        session = await service.create_signing_session(
            nda_id=nda_id,
            current_user_id=current_user_id,
        )

    except NDANotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except NDAAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except NDAAlreadySignedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except NDAAlreadyCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except NDASigningInitializationInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except SignatureProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Electronic signature service is unavailable.",
        ) from exc

    return NDASigningSessionResponse(
        signing_url=session.signing_url,
    )