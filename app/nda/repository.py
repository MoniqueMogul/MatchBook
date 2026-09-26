from datetime import timedelta, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.db_enum import NDASigningInitializationStatus
from app.db.db_model import (
    NDA,
    Match,
    BuyerProfile,
    SellerProfile,
    Business,
)


SIGNING_INITIALIZATION_TIMEOUT = timedelta(
    minutes=2
)

class NDARepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(
        self,
        nda_id: UUID,
        *,
        for_update: bool = False,
    ) -> NDA | None:

        stmt = (
            select(NDA)
            .where(NDA.id == nda_id)
        )

        if for_update:
            stmt = stmt.with_for_update()

        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_match_id(
        self,
        match_id: UUID,
        *,
        for_update: bool = False,
    ) -> NDA | None:

        stmt = (
            select(NDA)
            .where(NDA.match_id == match_id)
        )

        if for_update:
            stmt = stmt.with_for_update()

        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_provider_document_id(
            self,
            *,
            signature_provider: str,
            provider_document_id: str,
            for_update: bool = False,
    ) -> NDA | None:

        stmt = (
            select(NDA)
            .where(
                NDA.signature_provider == signature_provider,
                NDA.provider_document_id == provider_document_id,
            )
        )

        if for_update:
            stmt = stmt.with_for_update()

        return (
            self.db.execute(stmt)
            .scalar_one_or_none()
        )

    def get_with_match(
        self,
        nda_id: UUID,
    ) -> NDA | None:

        stmt = (
            select(NDA)
            .options(
                joinedload(NDA.match)
                .joinedload(Match.buyer),

                joinedload(NDA.match)
                .joinedload(Match.business),
            )
            .where(NDA.id == nda_id)
        )

        return (
            self.db.execute(stmt)
            .unique()
            .scalar_one_or_none()
        )

    def get_for_signing(
            self,
            *,
            nda_id: UUID,
            for_update: bool = False,
    ) -> NDA | None:

        stmt = (
            select(NDA)
            .where(NDA.id == nda_id)
            .options(
                joinedload(NDA.match)
                .joinedload(Match.buyer)
                .joinedload(BuyerProfile.user),

                joinedload(NDA.match)
                .joinedload(Match.business)
                .joinedload(Business.seller)
                .joinedload(SellerProfile.user),
            )
        )

        if for_update:
            stmt = stmt.with_for_update()

        return (
            self.db.execute(stmt)
            .unique()
            .scalar_one_or_none()
        )

    def create(
        self,
        *,
        match_id: UUID,
        document_id: UUID,
        version: str,
    ) -> NDA:

        nda = NDA(
            match_id=match_id,
            document_id=document_id,
            version=version,
        )

        self.db.add(nda)
        self.db.flush()

        return nda

    def attach_signature_provider(
            self,
            *,
            nda: NDA,
            signature_provider: str,
            provider_document_id: str,
            provider_template_id: str | None,
    ) -> NDA:

        nda.signature_provider = signature_provider
        nda.provider_document_id = provider_document_id
        nda.provider_template_id = provider_template_id

        nda.signing_initialization_status = (
            NDASigningInitializationStatus.READY
        )

        nda.signing_initialization_started_at = None

        self.db.flush()

        return nda

    def claim_signing_initialization(
            self,
            *,
            nda_id: UUID,
    ) -> bool:
        """
        Atomically claim responsibility for creating the external
        signature document.

        An active initialization claim blocks concurrent requests.

        A stale initialization claim may be reclaimed after the
        initialization timeout.
        """

        nda = self.get_by_id(
            nda_id,
            for_update=True,
        )

        if nda is None:
            return False

        # Provider document already exists.
        # There is nothing left to initialize.
        if nda.provider_document_id is not None:
            return False

        now = datetime.now(timezone.utc)

        if (
                nda.signing_initialization_status
                == NDASigningInitializationStatus.INITIALIZING
        ):
            started_at = (
                nda.signing_initialization_started_at
            )

            # INITIALIZING without a timestamp is an invalid/stale
            # legacy state. Allow it to be reclaimed.
            if started_at is not None:
                stale_before = (
                        now
                        - SIGNING_INITIALIZATION_TIMEOUT
                )

                if started_at > stale_before:
                    # Another request still owns a live claim.
                    return False

        # NOT_STARTED, FAILED, or stale INITIALIZING can claim.
        nda.signing_initialization_status = (
            NDASigningInitializationStatus.INITIALIZING
        )

        nda.signing_initialization_started_at = now

        self.db.flush()

        return True


    def mark_signing_initialization_failed(
            self,
            *,
            nda_id: UUID,
    ) -> None:

        nda = self.get_by_id(
            nda_id,
            for_update=True,
        )

        if nda is None:
            return

        if nda.provider_document_id is not None:
            return

        nda.signing_initialization_status = (
            NDASigningInitializationStatus.FAILED
        )

        self.db.flush()
