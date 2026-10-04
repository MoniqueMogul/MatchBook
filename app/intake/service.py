from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db.db_enum import EventType
from app.db.db_model import (
    Business,
    BuyerPreferences,
    BuyerProfile,
    OutboxEvent,
)
from app.events.payload_schema import (
    BusinessCreatedPayload,
    BuyerCreatedPayload,
)
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate
from app.intake.repository import IntakeRepository
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
from app.intake.validation import (
    business_readiness,
    buyer_preferences_readiness,
)


class IntakeService:

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.session = session

        self.repository = IntakeRepository(
            session
        )

        self.outbox_repository = OutboxRepository(
            session
        )

    # ========================================================
    # BUSINESS MATCHING EVENTS
    # ========================================================

    def _create_business_event_if_ready(
        self,
        business: Business,
        seller_user_id: UUID,
    ) -> OutboxEvent | None:
        """
        Stage the correct matching event for a matching-ready business.

        First time the business becomes matching-ready:
            BUSINESS_CREATED

        Every later matching-relevant update:
            BUSINESS_UPDATED

        The stable BUSINESS_CREATED idempotency key ensures the
        creation event can only exist once.

        BUSINESS_UPDATED events receive unique idempotency keys so
        every legitimate update can trigger a fresh matching run.
        """

        validated_business = (
            BusinessCreate.model_validate(
                business
            )
        )

        readiness = business_readiness(
            validated_business
        )

        if not readiness.ready:
            return None

        payload = BusinessCreatedPayload(
            business_id=business.id,
            seller_id=business.seller_id,
            seller_user_id=seller_user_id,
        )

        created_idempotency_key = (
            f"business_created:{business.id}"
        )

        existing_created_event = (
            self.outbox_repository.get_by_idempotency_key(
                created_idempotency_key
            )
        )

        if existing_created_event is None:
            return self.outbox_repository.create_event(
                OutboxEventCreate(
                    idempotency_key=created_idempotency_key,
                    event_type=EventType.BUSINESS_CREATED,
                    entity_type="business",
                    entity_id=business.id,
                    payload=payload.model_dump(
                        mode="json"
                    ),
                )
            )

        return self.outbox_repository.create_event(
            OutboxEventCreate(
                idempotency_key=(
                    f"business_updated:"
                    f"{business.id}:"
                    f"{uuid4()}"
                ),
                event_type=EventType.BUSINESS_UPDATED,
                entity_type="business",
                entity_id=business.id,
                payload=payload.model_dump(
                    mode="json"
                ),
            )
        )

    def create_business(
        self,
        seller_user_id: UUID,
        data: BusinessCreate,
        idempotency_key: str,
    ) -> Business:

        try:
            result = self.repository.create_business(
                seller_user_id,
                data,
                idempotency_key,
            )

            business = result.business

            if not result.created:
                return business

            outbox_event = (
                self._create_business_event_if_ready(
                    business,
                    seller_user_id,
                )
            )

            self.session.commit()

        except Exception:
            self.session.rollback()
            raise

        self.session.refresh(
            business
        )

        if outbox_event is not None:
            self._enqueue_outbox_event(
                outbox_event.id
            )

        return business

    def update_business(
        self,
        seller_user_id: UUID,
        business_id: UUID,
        data: BusinessUpdate,
    ) -> Business:

        try:
            business = self.repository.update_business(
                seller_user_id,
                business_id,
                data,
            )

            outbox_event = (
                self._create_business_event_if_ready(
                    business,
                    seller_user_id,
                )
            )

            self.session.commit()

        except Exception:
            self.session.rollback()
            raise

        self.session.refresh(
            business
        )

        if outbox_event is not None:
            self._enqueue_outbox_event(
                outbox_event.id
            )

        return business

    # ========================================================
    # OUTBOX ENQUEUE
    # ========================================================

    @staticmethod
    def _enqueue_outbox_event(
        event_id: UUID,
    ) -> None:

        from app.events.tasks import send_outbox_event

        send_outbox_event.delay(
            str(event_id)
        )

    # ========================================================
    # BUYER MATCHING EVENTS
    # ========================================================

    def _create_buyer_event_if_ready(
        self,
        preferences: BuyerPreferences,
        profile: BuyerProfile,
    ) -> OutboxEvent | None:
        """
        Stage the correct matching event for a matching-ready buyer.

        First time the buyer becomes matching-ready:
            BUYER_CREATED

        Every later matching-preference update:
            BUYER_PREFERENCES_UPDATED

        The stable BUYER_CREATED idempotency key ensures the creation
        event can only exist once.

        BUYER_PREFERENCES_UPDATED events receive unique idempotency
        keys so every legitimate preference update can trigger a
        fresh matching run.
        """

        validated = (
            BuyerPreferencesUpsert.model_validate(
                preferences
            )
        )

        readiness = buyer_preferences_readiness(
            validated
        )

        if not readiness.ready:
            return None

        payload = BuyerCreatedPayload(
            buyer_id=profile.id,
            user_id=profile.user_id,
        )

        created_idempotency_key = (
            f"buyer_created:{profile.id}"
        )

        existing_created_event = (
            self.outbox_repository.get_by_idempotency_key(
                created_idempotency_key
            )
        )

        if existing_created_event is None:
            return self.outbox_repository.create_event(
                OutboxEventCreate(
                    idempotency_key=created_idempotency_key,
                    event_type=EventType.BUYER_CREATED,
                    entity_type="buyer",
                    entity_id=profile.id,
                    payload=payload.model_dump(
                        mode="json"
                    ),
                )
            )

        return self.outbox_repository.create_event(
            OutboxEventCreate(
                idempotency_key=(
                    f"buyer_preferences_updated:"
                    f"{profile.id}:"
                    f"{uuid4()}"
                ),
                event_type=EventType.BUYER_PREFERENCES_UPDATED,
                entity_type="buyer",
                entity_id=profile.id,
                payload=payload.model_dump(
                    mode="json"
                ),
            )
        )

    # ========================================================
    # BUYER PROFILE
    # ========================================================

    def upsert_buyer_profile(
        self,
        user_id: UUID,
        data: BuyerProfileCreate | BuyerProfileUpdate,
    ) -> BuyerProfile:

        try:
            profile = (
                self.repository.upsert_buyer_profile(
                    user_id,
                    data,
                )
            )

            self.session.commit()

        except Exception:
            self.session.rollback()
            raise

        self.session.refresh(
            profile
        )

        return profile

    # ========================================================
    # BUYER PREFERENCES
    # ========================================================

    def upsert_buyer_preferences(
        self,
        user_id: UUID,
        data: BuyerPreferencesUpsert,
    ) -> BuyerPreferences:

        try:
            preferences = (
                self.repository.upsert_buyer_preferences(
                    user_id,
                    data,
                )
            )

            profile = (
                self.repository.get_buyer_profile_by_user_id(
                    user_id
                )
            )

            outbox_event = (
                self._create_buyer_event_if_ready(
                    preferences,
                    profile,
                )
            )

            self.session.commit()

        except Exception:
            self.session.rollback()
            raise

        self.session.refresh(
            preferences
        )

        if outbox_event is not None:
            self._enqueue_outbox_event(
                outbox_event.id
            )

        return preferences