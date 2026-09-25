import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.nda.service import (
    NDAService,
    NDAServiceError,
)

from app.nda.signing.exceptions import (
    SignatureProviderError,
    SignatureWebhookVerificationError,
)

from app.nda.signing.factory import (
    build_signature_provider,
)


router = APIRouter(
    prefix="/nda/webhooks",
    tags=["NDA Webhooks"],
)


@router.post(
    "/signwell",
    status_code=status.HTTP_200_OK,
)
async def signwell_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:

    raw_body = await request.body()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:
        payload = json.loads(raw_body)

    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        )



    # --------------------------------------------------------
    # Parse + verify provider event
    # --------------------------------------------------------

    try:
        provider = build_signature_provider()

        events = await provider.parse_webhook(
            payload=payload,
            headers=dict(request.headers),
            raw_body=raw_body,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Electronic signature service is not configured.",
        ) from exc

    except SignatureWebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook.",
        ) from exc

    except SignatureProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook verification unavailable.",
        ) from exc

    # --------------------------------------------------------
    # Apply events to Matchbook
    # --------------------------------------------------------

    service = NDAService(
        db=db,
        signature_provider=provider,
    )

    try:
        for event in events:
            service.process_signing_event(
                event=event,
            )

    except NDAServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook could not be processed.",
        ) from exc

    return {
        "received": True,
    }