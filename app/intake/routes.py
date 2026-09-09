from typing import NoReturn
from uuid import UUID
from app.db.db_enum import EventType
from app.events.router import publish_event


from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
)

from app.auth.dependencies import (
    get_current_user_id,
)
from app.intake.dependencies import (
    get_intake_repository,
)
from app.intake.repository import (
    IntakeConflictError,
    IntakeNotFoundError,
    IntakeRepository,
    IntakeRepositoryError,
)
from app.intake.schemas.business import (
    BusinessCreate,
    BusinessUpdate,
)
from app.intake.schemas.buyer import (
    BuyerProfileCreate,
    BuyerProfileUpdate,
)
from app.intake.schemas.buyer_preferences import (
    BuyerPreferencesUpsert,
)
from app.intake.schemas.responses import (
    BusinessRead,
    BuyerPreferencesRead,
    BuyerProfileRead,
    ReadinessResponse,
    SellerProfileRead,
)
from app.intake.schemas.seller import (
    SellerProfileCreate,
)
from app.intake.validation.readiness import (
    business_readiness,
    buyer_preferences_readiness,
)


router = APIRouter(
    prefix="/intake",
    tags=["intake"],
)


def _raise_http_error(
    exc: IntakeRepositoryError,
) -> NoReturn:

    if isinstance(
        exc,
        IntakeNotFoundError,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        IntakeConflictError,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    raise HTTPException(
        status_code=(
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ),
        detail="Unexpected Intake persistence error.",
    ) from exc


def _clean_idempotency_key(
    idempotency_key: str,
) -> str:

    cleaned = idempotency_key.strip()

    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Idempotency-Key header "
                "cannot be blank."
            ),
        )

    return cleaned


# ============================================================
# BUYER PROFILE
# ============================================================


@router.post(
    "/buyers/profile",
    response_model=BuyerProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_buyer_profile(
    payload: BuyerProfileCreate,
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerProfileRead:

    try:
        profile = (
            repository.create_buyer_profile(
                current_user_id,
                payload,
            )
        )

    except IntakeRepositoryError as exc:
        _raise_http_error(
            exc
        )

    publish_event(
        event_type=EventType.BUYER_CREATED,
        message={
            "event_type": (
                EventType.BUYER_CREATED.value
            ),
            "entity_type": "buyer",
            "entity_id": str(
                profile.id
            ),
            "payload": {
                "buyer_id": str(
                    profile.id
                ),
                "user_id": str(
                    profile.user_id
                ),
            },
        },
    )

    return BuyerProfileRead.model_validate(
        profile
    )

@router.get(
    "/buyers/profile",
    response_model=BuyerProfileRead,
)
def get_buyer_profile(
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerProfileRead:

    profile = (
        repository.get_buyer_profile_by_user_id(
            current_user_id
        )
    )

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Buyer profile does not exist "
                "for this user."
            ),
        )

    return BuyerProfileRead.model_validate(
        profile
    )


@router.patch(
    "/buyers/profile",
    response_model=BuyerProfileRead,
)
def update_buyer_profile(
    payload: BuyerProfileUpdate,
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerProfileRead:

    try:
        profile = (
            repository.update_buyer_profile(
                current_user_id,
                payload,
            )
        )

    except IntakeRepositoryError as exc:
        _raise_http_error(
            exc
        )

    return BuyerProfileRead.model_validate(
        profile
    )


# ============================================================
# BUYER PREFERENCES
# ============================================================


@router.get(
    "/buyers/preferences",
    response_model=BuyerPreferencesRead,
)
def get_buyer_preferences(
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerPreferencesRead:

    preferences = (
        repository.get_buyer_preferences_by_user_id(
            current_user_id
        )
    )

    if preferences is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Buyer preferences do not exist "
                "for this user."
            ),
        )

    return BuyerPreferencesRead.model_validate(
        preferences
    )


@router.put(
    "/buyers/preferences",
    response_model=BuyerPreferencesRead,
)
def upsert_buyer_preferences(
    payload: BuyerPreferencesUpsert,
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerPreferencesRead:

    try:
        preferences = (
            repository.upsert_buyer_preferences(
                current_user_id,
                payload,
            )
        )

    except IntakeRepositoryError as exc:
        _raise_http_error(
            exc
        )

    return BuyerPreferencesRead.model_validate(
        preferences
    )


@router.get(
    "/buyers/readiness",
    response_model=ReadinessResponse,
)
def get_buyer_readiness(
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> ReadinessResponse:

    preferences = (
        repository.get_buyer_preferences_by_user_id(
            current_user_id
        )
    )

    if preferences is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Buyer preferences do not exist "
                "for this user."
            ),
        )

    validated = (
        BuyerPreferencesUpsert.model_validate(
            preferences
        )
    )

    result = buyer_preferences_readiness(
        validated
    )

    return ReadinessResponse(
        ready=result.ready,
        missing_fields=result.missing_fields,
    )


# ============================================================
# SELLER PROFILE
# ============================================================


@router.post(
    "/sellers/profile",
    response_model=SellerProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_seller_profile(
    payload: SellerProfileCreate,
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> SellerProfileRead:

    try:
        profile = (
            repository.create_seller_profile(
                current_user_id,
                payload,
            )
        )

    except IntakeRepositoryError as exc:
        _raise_http_error(
            exc
        )

    return SellerProfileRead.model_validate(
        profile
    )


@router.get(
    "/sellers/profile",
    response_model=SellerProfileRead,
)
def get_seller_profile(
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> SellerProfileRead:

    profile = (
        repository.get_seller_profile_by_user_id(
            current_user_id
        )
    )

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Seller profile does not exist "
                "for this user."
            ),
        )

    return SellerProfileRead.model_validate(
        profile
    )


# ============================================================
# SELLER BUSINESSES
# ============================================================


@router.post(
    "/sellers/businesses",
    response_model=BusinessRead,
    status_code=status.HTTP_201_CREATED,
)
def create_business(
    payload: BusinessCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
    ),
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BusinessRead:

    cleaned_key = _clean_idempotency_key(
        idempotency_key
    )

    try:
        (
            business,
            was_created,
        ) = repository.create_business(
            current_user_id,
            payload,
            cleaned_key,
        )

    except IntakeRepositoryError as exc:
        _raise_http_error(
            exc
        )

    if was_created:
        publish_event(
            event_type=(
                EventType.BUSINESS_CREATED
            ),
            message={
                "event_type": (
                    EventType
                    .BUSINESS_CREATED
                    .value
                ),
                "entity_type": "business",
                "entity_id": str(
                    business.id
                ),
                "payload": {
                    "business_id": str(
                        business.id
                    ),
                    "seller_id": str(
                        business.seller_id
                    ),
                    "seller_user_id": str(
                        current_user_id
                    ),
                },
            },
        )

    return BusinessRead.model_validate(
        business
    )

@router.get(
    "/sellers/businesses",
    response_model=list[BusinessRead],
)
def list_businesses(
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> list[BusinessRead]:

    try:
        businesses = (
            repository.list_businesses_for_seller(
                current_user_id
            )
        )

    except IntakeRepositoryError as exc:
        _raise_http_error(
            exc
        )

    return [
        BusinessRead.model_validate(
            item
        )
        for item in businesses
    ]


@router.get(
    "/sellers/businesses/{business_id}",
    response_model=BusinessRead,
)
def get_business(
    business_id: UUID,
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BusinessRead:

    business = (
        repository.get_business_for_seller(
            current_user_id,
            business_id,
        )
    )

    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Business does not exist "
                "for this seller."
            ),
        )

    return BusinessRead.model_validate(
        business
    )


@router.patch(
    "/sellers/businesses/{business_id}",
    response_model=BusinessRead,
)
def update_business(
    business_id: UUID,
    payload: BusinessUpdate,
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BusinessRead:

    try:
        business = (
            repository.update_business(
                current_user_id,
                business_id,
                payload,
            )
        )

    except IntakeRepositoryError as exc:
        _raise_http_error(
            exc
        )

    return BusinessRead.model_validate(
        business
    )


@router.get(
    "/sellers/businesses/{business_id}/readiness",
    response_model=ReadinessResponse,
)
def get_business_readiness(
    business_id: UUID,
    current_user_id: UUID = Depends(
        get_current_user_id
    ),
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> ReadinessResponse:

    business = (
        repository.get_business_for_seller(
            current_user_id,
            business_id,
        )
    )

    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Business does not exist "
                "for this seller."
            ),
        )

    validated = BusinessCreate.model_validate(
        business
    )

    result = business_readiness(
        validated
    )

    return ReadinessResponse(
        ready=result.ready,
        missing_fields=result.missing_fields,
    )