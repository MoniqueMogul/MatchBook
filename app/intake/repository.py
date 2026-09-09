from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.db_model import (
    Business,
    BuyerPreferences,
    BuyerProfile,
    SellerProfile,
    User,
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
from app.intake.schemas.seller import SellerProfileCreate


class IntakeRepositoryError(Exception):
    """Base exception for expected Intake persistence failures."""


class IntakeNotFoundError(IntakeRepositoryError):
    """Raised when a required Intake record does not exist."""


class IntakeConflictError(IntakeRepositoryError):
    """Raised when persisted state conflicts with an Intake write."""


class IntakeRepository:
    """
    Persistence boundary for Intake and Profile Management.

    This class reads and writes shared SQLAlchemy models.
    It does not perform matching or verification.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # --------------------------------------------------------
    # Shared helpers
    # --------------------------------------------------------

    def _require_user(
        self,
        user_id: UUID,
    ) -> User:

        user = self.session.scalar(
            select(User).where(
                User.id == user_id
            )
        )

        if user is None:
            raise IntakeNotFoundError(
                f"User {user_id} does not exist."
            )

        return user

    def _commit_and_refresh(
        self,
        entity: object,
    ) -> None:

        try:
            self.session.commit()

        except IntegrityError as exc:
            self.session.rollback()

            raise IntakeConflictError(
                "Database constraints prevented the Intake write."
            ) from exc

        self.session.refresh(entity)

    # ========================================================
    # BUYER PROFILE
    # ========================================================

    def get_buyer_profile_by_user_id(
        self,
        user_id: UUID,
    ) -> BuyerProfile | None:

        return self.session.scalar(
            select(BuyerProfile).where(
                BuyerProfile.user_id == user_id
            )
        )

    def create_buyer_profile(
        self,
        user_id: UUID,
        data: BuyerProfileCreate,
    ) -> BuyerProfile:

        self._require_user(user_id)

        existing = self.get_buyer_profile_by_user_id(
            user_id
        )

        if existing is not None:
            raise IntakeConflictError(
                "Buyer profile already exists for this user."
            )

        profile = BuyerProfile(
            user_id=user_id,
            **data.model_dump(),
        )

        self.session.add(profile)

        self._commit_and_refresh(profile)

        return profile

    def update_buyer_profile(
        self,
        user_id: UUID,
        data: BuyerProfileUpdate,
    ) -> BuyerProfile:

        profile = self.get_buyer_profile_by_user_id(
            user_id
        )

        if profile is None:
            raise IntakeNotFoundError(
                "Buyer profile does not exist for this user."
            )

        changes = data.model_dump(
            exclude_unset=True
        )

        for field, value in changes.items():
            setattr(
                profile,
                field,
                value,
            )

        self._commit_and_refresh(profile)

        return profile

    # ========================================================
    # BUYER PREFERENCES
    # ========================================================

    def get_buyer_preferences_by_user_id(
        self,
        user_id: UUID,
    ) -> BuyerPreferences | None:

        statement = (
            select(BuyerPreferences)
            .join(
                BuyerProfile,
                BuyerPreferences.buyer_id
                == BuyerProfile.id,
            )
            .where(
                BuyerProfile.user_id == user_id
            )
        )

        return self.session.scalar(
            statement
        )

    def upsert_buyer_preferences(
        self,
        user_id: UUID,
        data: BuyerPreferencesUpsert,
    ) -> BuyerPreferences:

        profile = self.get_buyer_profile_by_user_id(
            user_id
        )

        if profile is None:
            raise IntakeNotFoundError(
                "Create the buyer profile before "
                "saving preferences."
            )

        payload = data.model_dump(
            exclude_unset=True
        )

        preferences = (
            self.get_buyer_preferences_by_user_id(
                user_id
            )
        )

        if preferences is None:
            preferences = BuyerPreferences(
                buyer_id=profile.id,
                **payload,
            )

            self.session.add(
                preferences
            )

        else:
            for field, value in payload.items():
                setattr(
                    preferences,
                    field,
                    value,
                )

        self._commit_and_refresh(
            preferences
        )

        return preferences

    # ========================================================
    # SELLER PROFILE
    # ========================================================

    def get_seller_profile_by_user_id(
        self,
        user_id: UUID,
    ) -> SellerProfile | None:

        return self.session.scalar(
            select(SellerProfile).where(
                SellerProfile.user_id == user_id
            )
        )

    def create_seller_profile(
        self,
        user_id: UUID,
        data: SellerProfileCreate,
    ) -> SellerProfile:

        # SellerProfileCreate currently has no
        # seller-entered fields.
        del data

        self._require_user(user_id)

        existing = (
            self.get_seller_profile_by_user_id(
                user_id
            )
        )

        if existing is not None:
            raise IntakeConflictError(
                "Seller profile already exists for this user."
            )

        profile = SellerProfile(
            user_id=user_id
        )

        self.session.add(
            profile
        )

        self._commit_and_refresh(
            profile
        )

        return profile

    # ========================================================
    # BUSINESSES
    # ========================================================

    def list_businesses_for_seller(
        self,
        seller_user_id: UUID,
    ) -> list[Business]:

        seller = (
            self.get_seller_profile_by_user_id(
                seller_user_id
            )
        )

        if seller is None:
            raise IntakeNotFoundError(
                "Seller profile does not exist for this user."
            )

        statement = (
            select(Business)
            .where(
                Business.seller_id
                == seller.id
            )
            .order_by(
                Business.created_at.desc()
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def _get_business_by_idempotency_key(
        self,
        seller_id: UUID,
        idempotency_key: str,
    ) -> Business | None:

        return self.session.scalar(
            select(Business).where(
                Business.seller_id == seller_id,
                Business.idempotency_key
                == idempotency_key,
            )
        )

    def create_business(
        self,
        seller_user_id: UUID,
        data: BusinessCreate,
        idempotency_key: str,
    ) -> tuple[Business, bool]:

        seller = (
            self.get_seller_profile_by_user_id(
                seller_user_id
            )
        )

        if seller is None:
            raise IntakeNotFoundError(
                "Create the seller profile before "
                "creating a business."
            )

        existing = (
            self._get_business_by_idempotency_key(
                seller.id,
                idempotency_key,
            )
        )

        if existing is not None:
            return (
                existing,
                False,
            )

        business = Business(
            seller_id=seller.id,
            idempotency_key=idempotency_key,
            **data.model_dump(),
        )

        self.session.add(
            business
        )

        try:
            self.session.commit()

        except IntegrityError as exc:
            self.session.rollback()

            # Another identical request may have
            # created the row between our initial
            # SELECT and COMMIT.
            existing = (
                self._get_business_by_idempotency_key(
                    seller.id,
                    idempotency_key,
                )
            )

            if existing is not None:
                return (
                    existing,
                    False,
                )

            raise IntakeConflictError(
                "Database constraints prevented "
                "the business from being created."
            ) from exc

        self.session.refresh(
            business
        )

        return (
            business,
            True,
        )

    def get_business_for_seller(
        self,
        seller_user_id: UUID,
        business_id: UUID,
    ) -> Business | None:

        statement = (
            select(Business)
            .join(
                SellerProfile,
                Business.seller_id
                == SellerProfile.id,
            )
            .where(
                Business.id == business_id,
                SellerProfile.user_id
                == seller_user_id,
            )
        )

        return self.session.scalar(
            statement
        )

    def update_business(
        self,
        seller_user_id: UUID,
        business_id: UUID,
        data: BusinessUpdate,
    ) -> Business:

        business = self.get_business_for_seller(
            seller_user_id,
            business_id,
        )

        if business is None:
            raise IntakeNotFoundError(
                "Business does not exist for this seller."
            )

        changes = data.model_dump(
            exclude_unset=True
        )

        for field, value in changes.items():
            setattr(
                business,
                field,
                value,
            )

        self._commit_and_refresh(
            business
        )

        return business