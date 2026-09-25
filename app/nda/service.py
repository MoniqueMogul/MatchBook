from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import NDAStatus, EventType
from app.db.db_model import NDA

from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate

from app.nda.repository import NDARepository

from app.nda.signing.base import SignatureProvider
from app.nda.signing.enums import (
    SignerRole,
    SigningEventType, SignatureProviderType,
)
from app.nda.signing.exceptions import SignatureProviderError, SignatureProviderRequestError
from app.nda.signing.schemas import (
    Signer,
    SigningEvent,
    SigningSession,
)

from app.verification.services.nda_eligibility import NDAEligibilityService


# ============================================================
# EXCEPTIONS
# ============================================================

class NDAServiceError(Exception):
    """Base exception for expected NDA workflow errors."""


class NDANotFoundError(NDAServiceError):
    pass


class NDAAccessDeniedError(NDAServiceError):
    pass


class NDAAlreadySignedError(NDAServiceError):
    pass


class NDAAlreadyCompletedError(NDAServiceError):
    pass

class NDASigningInitializationInProgressError(NDAServiceError):
    pass


class NDASigningInitializationError(NDAServiceError):
    pass


# ============================================================
# SERVICE
# ============================================================

class NDAService:

    def __init__(
            self,
            db: Session,
            *,
            signature_provider: SignatureProvider,
            repository: NDARepository | None = None,
            outbox_repository: OutboxRepository | None = None,
            verification_service: NDAEligibilityService | None = None,
    ) -> None:

        self.db = db

        self.repository = (
                repository
                or NDARepository(db)
        )

        self.outbox_repository = (
                outbox_repository
                or OutboxRepository(db)
        )

        self.verification_service = (
                verification_service
                or NDAEligibilityService(db)
        )

        self.signature_provider = signature_provider

    # ========================================================
    # SIGN NDA
    # ========================================================

    async def create_signing_session(
            self,
            *,
            provider_document_id: str,
            signer: Signer,
    ) -> SigningSession:

        data = await self._get_document_data(
            provider_document_id=provider_document_id,
        )

        expected_recipient_id = (
            self._recipient_id_for_role(
                signer.role
            )
        )

        for recipient in data.get("recipients", []):

            if str(recipient.get("id")) != expected_recipient_id:
                continue

            recipient_email = (
                    recipient.get("email") or ""
            ).strip().lower()

            signer_email = signer.email.strip().lower()

            if recipient_email != signer_email:
                raise SignatureProviderRequestError(
                    "SignWell recipient identity does not "
                    "match the authenticated signer."
                )

            signing_url = recipient.get(
                "embedded_signing_url"
            )

            if not signing_url:
                raise SignatureProviderRequestError(
                    "SignWell did not return an "
                    "embedded signing URL."
                )

            return SigningSession(
                provider=SignatureProviderType.SIGNWELL,
                provider_document_id=provider_document_id,
                signing_url=signing_url,
            )

        raise SignatureProviderRequestError(
            "Signer was not found on the "
            "SignWell document."
        )

    # ========================================================
    # AUTHORIZATION
    # ========================================================

    @staticmethod
    def _get_signer_role(
            *,
            nda: NDA,
            current_user_id: UUID,
    ) -> SignerRole:

        match = nda.match

        if current_user_id == match.buyer.user_id:
            return SignerRole.BUYER

        if current_user_id == match.business.seller.user_id:
            return SignerRole.SELLER

        raise NDAAccessDeniedError(
            "You are not a party to this NDA."
        )

    # ========================================================
    # NDA STATE MACHINE
    # ========================================================

    @staticmethod
    def _update_status(
            *,
            nda: NDA,
            now: datetime,
    ) -> bool:

        buyer_signed = (
                nda.buyer_signed_at is not None
        )

        seller_signed = (
                nda.seller_signed_at is not None
        )

        if buyer_signed and seller_signed:

            if nda.status == NDAStatus.COMPLETED:
                return False

            nda.status = NDAStatus.COMPLETED
            nda.completed_at = now

            return True

        if buyer_signed:
            nda.status = NDAStatus.BUYER_SIGNED
            return False

        if seller_signed:
            nda.status = NDAStatus.SELLER_SIGNED
            return False

        nda.status = NDAStatus.PENDING

        return False

    # ========================================================
    # OUTBOX
    # ========================================================

    def _create_completed_event(
            self,
            *,
            nda: NDA,
    ) -> None:

        idempotency_key = (
            f"nda-completed:{nda.id}"
        )

        existing_event = (
            self.outbox_repository
            .get_by_idempotency_key(
                idempotency_key
            )
        )

        if existing_event is not None:
            return

        event = OutboxEventCreate(
            event_type=EventType.NDA_COMPLETED,
            entity_type="nda",
            entity_id=nda.id,
            idempotency_key=idempotency_key,
            payload={
                "nda_id": str(nda.id),
                "match_id": str(nda.match_id),
            },
        )

        self.outbox_repository.create_event(
            event
        )

    @staticmethod
    def _build_signer(
            *,
            nda: NDA,
            role: SignerRole,
    ) -> Signer:

        match = nda.match

        if role == SignerRole.BUYER:
            user = match.buyer.user

        else:
            user = match.business.seller.user

        if not user.email:
            raise NDAServiceError(
                "Signer does not have an email address."
            )

        name = f"{user.first_name} {user.last_name}".strip()

        return Signer(
            user_id=user.id,
            role=role,
            name=name,
            email=user.email,
        )

    def process_signing_event(
            self,
            *,
            event: SigningEvent,
    ) -> NDA:

        nda = self.repository.get_by_provider_document_id(
            signature_provider=event.provider.value,
            provider_document_id=event.provider_document_id,
            for_update=True,
        )

        if nda is None:
            raise NDANotFoundError(
                "NDA for signature document was not found."
            )

        # Critical protection:
        # don't allow an event from one provider to modify
        # an NDA owned by another provider.
        if nda.signature_provider != event.provider.value:
            raise NDAAccessDeniedError(
                "Signature provider does not match NDA provider."
            )

        # Duplicate webhook after completion.
        if nda.status == NDAStatus.COMPLETED:
            return nda

        now = event.occurred_at or datetime.now(timezone.utc)

        if event.event_type == SigningEventType.SIGNER_SIGNED:

            self._apply_signer_signed_event(
                nda=nda,
                event=event,
                now=now,
            )

        elif event.event_type == SigningEventType.DOCUMENT_COMPLETED:

            self._apply_document_completed_event(
                nda=nda,
            )

        became_completed = self._update_status(
            nda=nda,
            now=now,
        )

        if became_completed:
            self._create_completed_event(
                nda=nda,
            )

        self.db.commit()
        self.db.refresh(nda)

        return nda

    @staticmethod
    def _apply_signer_signed_event(
            *,
            nda: NDA,
            event: SigningEvent,
            now: datetime,
    ) -> None:

        if event.signer_role == SignerRole.BUYER:

            # Idempotent webhook handling.
            if nda.buyer_signed_at is None:
                nda.buyer_signed_at = now

            return

        if event.signer_role == SignerRole.SELLER:

            if nda.seller_signed_at is None:
                nda.seller_signed_at = now

            return

        raise NDAServiceError(
            "Signature event does not identify a valid signer."
        )

    @staticmethod
    def _apply_document_completed_event(
            *,
            nda: NDA,
    ) -> None:

        # DOCUMENT_COMPLETED means the provider says the entire
        # signing workflow has completed.
        #
        # We still require both signer events to have been
        # recorded before Matchbook considers the NDA complete.

        if (
                nda.buyer_signed_at is None
                or nda.seller_signed_at is None
        ):
            return

    async def initialize_signing(
            self,
            *,
            nda_id: UUID,
            current_user_id: UUID,
    ) -> NDA:

        nda = self.repository.get_for_signing(
            nda_id=nda_id,
        )

        if nda is None:
            raise NDANotFoundError(
                f"NDA {nda_id} was not found."
            )

        # --------------------------------------------------------
        # Authorization
        # --------------------------------------------------------

        self._get_signer_role(
            nda=nda,
            current_user_id=current_user_id,
        )

        # --------------------------------------------------------
        # Verification gate
        # --------------------------------------------------------

        self.verification_service.require_nda_eligibility(
            match_id=nda.match_id,
        )

        if nda.status == NDAStatus.COMPLETED:
            raise NDAAlreadyCompletedError(
                "This NDA has already been completed."
            )

        # --------------------------------------------------------
        # Idempotency
        # --------------------------------------------------------
        #
        # If we've already created the provider document,
        # DO NOT create another one.

        if nda.provider_document_id is not None:
            return nda

        # --------------------------------------------------------
        # Build signers
        # --------------------------------------------------------

        buyer = self._build_signer(
            nda=nda,
            role=SignerRole.BUYER,
        )

        seller = self._build_signer(
            nda=nda,
            role=SignerRole.SELLER,
        )

        # --------------------------------------------------------
        # Fields inserted into the NDA template
        # --------------------------------------------------------

        fields = self._build_document_fields(
            nda=nda,
        )

        # --------------------------------------------------------
        # External signature document
        # --------------------------------------------------------

        document = await self.signature_provider.create_document(
            signers=[
                buyer,
                seller,
            ],
            template_version=nda.version,
            fields=fields,
        )

        # --------------------------------------------------------
        # Save provider mapping
        # --------------------------------------------------------

        self.repository.attach_signature_provider(
            nda=nda,
            signature_provider=document.provider.value,
            provider_document_id=document.provider_document_id,
            provider_template_id=document.provider_template_id,
        )

        self.db.commit()
        self.db.refresh(nda)

        return nda

    @staticmethod
    @staticmethod
    def _build_document_fields(*, nda: NDA) -> dict[str, str]:
        buyer_user = nda.match.buyer.user
        seller_user = nda.match.business.seller.user
        business = nda.match.business

        buyer_name = (
            f"{buyer_user.first_name} {buyer_user.last_name}"
        ).strip()

        seller_name = (
            f"{seller_user.first_name} {seller_user.last_name}"
        ).strip()

        if not business.legal_name:
            raise NDAServiceError(
                "Business legal name is required before creating an NDA."
            )

        return {
            "buyer_name": buyer_name,
            "seller_name": seller_name,
            "business_name": business.legal_name,
        }

    async def _ensure_signature_document(
            self,
            *,
            nda_id: UUID,
            current_user_id: UUID,
    ) -> NDA:

        # --------------------------------------------------------
        # Phase 1: inspect NDA
        # --------------------------------------------------------

        nda = self.repository.get_for_signing(
            nda_id=nda_id,
            for_update=False,
        )

        if nda is None:
            raise NDANotFoundError(
                f"NDA {nda_id} was not found."
            )

        self._get_signer_role(
            nda=nda,
            current_user_id=current_user_id,
        )

        self.verification_service.require_nda_eligibility(
            match_id=nda.match_id,
        )

        if nda.provider_document_id is not None:
            return nda

        # End whatever read transaction SQLAlchemy currently has
        # before taking the short initialization claim.
        self.db.rollback()

        # --------------------------------------------------------
        # Phase 2: atomically claim initialization
        # --------------------------------------------------------

        claimed = (
            self.repository.claim_signing_initialization(
                nda_id=nda_id,
            )
        )

        if not claimed:

            self.db.rollback()

            nda = self.repository.get_for_signing(
                nda_id=nda_id,
                for_update=False,
            )

            if nda is None:
                raise NDANotFoundError(
                    f"NDA {nda_id} was not found."
                )

            if nda.provider_document_id is not None:
                return nda

            raise NDASigningInitializationInProgressError(
                "NDA signing is currently being initialized."
            )

        # COMMIT THE CLAIM.
        #
        # This releases the database row lock BEFORE we call
        # SignWell.
        self.db.commit()

        # --------------------------------------------------------
        # Phase 3: reload data required for provider
        # --------------------------------------------------------

        nda = self.repository.get_for_signing(
            nda_id=nda_id,
            for_update=False,
        )

        if nda is None:
            raise NDANotFoundError(
                f"NDA {nda_id} was not found."
            )

        buyer = self._build_signer(
            nda=nda,
            role=SignerRole.BUYER,
        )

        seller = self._build_signer(
            nda=nda,
            role=SignerRole.SELLER,
        )

        fields = self._build_document_fields(
            nda=nda,
        )

        template_version = nda.version
        # Finish the read transaction before external I/O.
        # We now have everything SignWell needs as plain Python data.
        # End the DB transaction before external network I/O.
        self.db.rollback()

        # --------------------------------------------------------
        # Phase 4: external provider call
        # --------------------------------------------------------

        try:

            document = (
                await self.signature_provider.create_document(
                    signers=[
                        buyer,
                        seller,
                    ],
                    template_version=nda.version,
                    fields=fields,
                )
            )

        except SignatureProviderError:

            self.repository.mark_signing_initialization_failed(
                nda_id=nda_id,
            )

            self.db.commit()

            raise

        # --------------------------------------------------------
        # Phase 5: persist provider result
        # --------------------------------------------------------

        nda = self.repository.get_by_id(
            nda_id,
            for_update=True,
        )

        if nda is None:
            self.db.rollback()

            raise NDANotFoundError(
                f"NDA {nda_id} was not found."
            )

        self.repository.attach_signature_provider(
            nda=nda,
            signature_provider=document.provider.value,
            provider_document_id=document.provider_document_id,
            provider_template_id=document.provider_template_id,
        )

        self.db.commit()
        self.db.refresh(nda)

        return nda