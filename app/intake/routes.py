from typing import NoReturn
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
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


# TODO:
# Once the team provides the shared Supabase Auth
# dependency, replace user_id path parameters with
# the authenticated user's UUID.


# ============================================================
# BUYER PROFILE
# ============================================================


@router.post(
    "/buyers/{user_id}/profile",
    response_model=BuyerProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_buyer_profile(
    user_id: UUID,
    payload: BuyerProfileCreate,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerProfileRead:

    try:
        profile = (
            repository.create_buyer_profile(
                user_id,
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


@router.get(
    "/buyers/{user_id}/profile",
    response_model=BuyerProfileRead,
)
def get_buyer_profile(
    user_id: UUID,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerProfileRead:

    profile = (
        repository.get_buyer_profile_by_user_id(
            user_id
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
    "/buyers/{user_id}/profile",
    response_model=BuyerProfileRead,
)
def update_buyer_profile(
    user_id: UUID,
    payload: BuyerProfileUpdate,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerProfileRead:

    try:
        profile = (
            repository.update_buyer_profile(
                user_id,
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
    "/buyers/{user_id}/preferences",
    response_model=BuyerPreferencesRead,
)
def get_buyer_preferences(
    user_id: UUID,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerPreferencesRead:

    preferences = (
        repository.get_buyer_preferences_by_user_id(
            user_id
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
    "/buyers/{user_id}/preferences",
    response_model=BuyerPreferencesRead,
)
def upsert_buyer_preferences(
    user_id: UUID,
    payload: BuyerPreferencesUpsert,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BuyerPreferencesRead:

    try:
        preferences = (
            repository.upsert_buyer_preferences(
                user_id,
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
    "/buyers/{user_id}/readiness",
    response_model=ReadinessResponse,
)
def get_buyer_readiness(
    user_id: UUID,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> ReadinessResponse:

    preferences = (
        repository.get_buyer_preferences_by_user_id(
            user_id
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
    "/sellers/{user_id}/profile",
    response_model=SellerProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_seller_profile(
    user_id: UUID,
    payload: SellerProfileCreate,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> SellerProfileRead:

    try:
        profile = (
            repository.create_seller_profile(
                user_id,
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
    "/sellers/{user_id}/profile",
    response_model=SellerProfileRead,
)
def get_seller_profile(
    user_id: UUID,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> SellerProfileRead:

    profile = (
        repository.get_seller_profile_by_user_id(
            user_id
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
    "/sellers/{user_id}/businesses",
    response_model=BusinessRead,
    status_code=status.HTTP_201_CREATED,
)
def create_business(
    user_id: UUID,
    payload: BusinessCreate,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BusinessRead:

    try:
        business = (
            repository.create_business(
                user_id,
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
    "/sellers/{user_id}/businesses",
    response_model=list[BusinessRead],
)
def list_businesses(
    user_id: UUID,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> list[BusinessRead]:

    try:
        businesses = (
            repository.list_businesses_for_seller(
                user_id
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
    "/sellers/{user_id}/businesses/{business_id}",
    response_model=BusinessRead,
)
def get_business(
    user_id: UUID,
    business_id: UUID,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BusinessRead:

    business = (
        repository.get_business_for_seller(
            user_id,
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
    "/sellers/{user_id}/businesses/{business_id}",
    response_model=BusinessRead,
)
def update_business(
    user_id: UUID,
    business_id: UUID,
    payload: BusinessUpdate,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> BusinessRead:

    try:
        business = (
            repository.update_business(
                user_id,
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
    (
        "/sellers/{user_id}/businesses/"
        "{business_id}/readiness"
    ),
    response_model=ReadinessResponse,
)
def get_business_readiness(
    user_id: UUID,
    business_id: UUID,
    repository: IntakeRepository = Depends(
        get_intake_repository
    ),
) -> ReadinessResponse:

    business = (
        repository.get_business_for_seller(
            user_id,
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