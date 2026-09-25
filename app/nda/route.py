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
    prefix="/webhooks",
    tags=["Webhooks"],
)


@router.post(
    "/signwell",
    status_code=status.HTTP_200_OK,
)
async def signwell_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:

    # --------------------------------------------------------
    # Raw body
    # --------------------------------------------------------

    raw_body = await request.body()

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    try:
        payload = json.loads(raw_body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        )

    # --------------------------------------------------------
    # Provider
    # --------------------------------------------------------

    provider = build_signature_provider()

    # --------------------------------------------------------
    # Parse + verify provider event
    # --------------------------------------------------------

    try:

        events = await provider.parse_webhook(
            payload=payload,
            headers=dict(request.headers),
            raw_body=raw_body,
        )

    except SignatureWebhookVerificationError:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook.",
        )

    except SignatureProviderError:

        # Provider could not be reached/verified.
        #
        # Return 503 rather than 200 so SignWell can retry
        # instead of us silently losing the event.

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook verification unavailable.",
        )

    # --------------------------------------------------------
    # Process Matchbook events
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

    except NDAServiceError:

        # Do not leak internal NDA/business details
        # back to an external provider.

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook could not be processed.",
        )

    return {
        "received": True,
    }