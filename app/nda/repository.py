from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.db_model import (
    NDA,
    Match,
    BuyerProfile,
    SellerProfile,
    Business,
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
        provider_document_id: str,
        for_update: bool = False,
    ) -> NDA | None:
        """
        Find the Matchbook NDA associated with an external
        signature-provider document.

        This is primarily used when processing provider webhooks.
        """

        stmt = (
            select(NDA)
            .where(
                NDA.provider_document_id == provider_document_id
            )
        )

        if for_update:
            stmt = stmt.with_for_update()

        return self.db.execute(stmt).scalar_one_or_none()

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
    ) -> NDA | None:
        """
        Load the NDA, buyer, seller, business and users required
        for signing.

        The NDA row is locked so two concurrent signing operations
        cannot modify its state at the same time.
        """

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
            .with_for_update()
        )

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
        """
        Associate an existing Matchbook NDA with the document
        created by the configured electronic-signature provider.
        """

        nda.signature_provider = signature_provider
        nda.provider_document_id = provider_document_id
        nda.provider_template_id = provider_template_id

        self.db.flush()

        return nda