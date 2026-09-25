from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.db_enum import EventType, VerificationStatus
from app.db.db_model import (
    Business,
    BusinessFinancials,
    BuyerFinancials,
    BuyerProfile,
    Declaration,
    Document,
    Match,
    SellerProfile,
    User,
)
from app.events.repository import OutboxRepository
from app.events.schema import OutboxEventCreate
from app.verification.exceptions import ResourceNotFoundError


class VerificationRepository:
    """Persistence boundary. Callers own commit and rollback."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def require_match_verification_context(self, match_id: UUID) -> Match:
        """Load every authoritative record used by the NDA eligibility gate."""
        statement = (
            select(Match)
            .options(
                joinedload(Match.buyer).joinedload(BuyerProfile.user),
                joinedload(Match.buyer).joinedload(BuyerProfile.financials),
                joinedload(Match.business)
                .joinedload(Business.seller)
                .joinedload(SellerProfile.user),
                joinedload(Match.business)
                .joinedload(Business.financials)
                .joinedload(BusinessFinancials.documents),
            )
            .where(Match.id == match_id)
        )
        match = self.session.execute(statement).unique().scalar_one_or_none()
        if match is None:
            raise ResourceNotFoundError("Match not found")
        return match

    def require_owned_buyer_financials(
        self,
        financials_id: UUID,
        user_id: UUID,
    ) -> BuyerFinancials:
        financials = self.session.scalar(
            select(BuyerFinancials)
            .join(BuyerProfile, BuyerFinancials.buyer_id == BuyerProfile.id)
            .where(
                BuyerFinancials.id == financials_id,
                BuyerProfile.user_id == user_id,
            )
        )
        if financials is None:
            raise ResourceNotFoundError("Buyer financials not found")
        return financials

    def require_owned_business_financials(
        self,
        financials_id: UUID,
        user_id: UUID,
    ) -> BusinessFinancials:
        financials = self.session.scalar(
            select(BusinessFinancials)
            .join(Business, BusinessFinancials.business_id == Business.id)
            .join(SellerProfile, Business.seller_id == SellerProfile.id)
            .where(
                BusinessFinancials.id == financials_id,
                SellerProfile.user_id == user_id,
            )
        )
        if financials is None:
            raise ResourceNotFoundError("Business financials not found")
        return financials

    def list_documents_for_buyer_financials(
        self,
        financials_id: UUID,
    ) -> list[Document]:
        return list(
            self.session.scalars(
                select(Document)
                .where(Document.buyer_financials_id == financials_id)
                .order_by(Document.uploaded_at.desc(), Document.id.desc())
            ).all()
        )

    def list_documents_for_business_financials(
        self,
        financials_id: UUID,
    ) -> list[Document]:
        return list(
            self.session.scalars(
                select(Document)
                .where(Document.business_financials_id == financials_id)
                .order_by(Document.uploaded_at.desc(), Document.id.desc())
            ).all()
        )

    def require_owned_business(
        self,
        business_id: UUID,
        user_id: UUID,
    ) -> Business:
        business = self.session.scalar(
            select(Business)
            .join(SellerProfile, Business.seller_id == SellerProfile.id)
            .where(
                Business.id == business_id,
                SellerProfile.user_id == user_id,
            )
        )
        if business is None:
            raise ResourceNotFoundError("Business not found")
        return business

    def require_user(self, user_id: UUID) -> User:
        user = self.session.scalar(select(User).where(User.id == user_id))
        if user is None:
            raise ResourceNotFoundError("User not found")
        return user

    def require_owned_document(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> Document:
        document = self.session.scalar(
            select(Document)
            .outerjoin(
                BuyerFinancials,
                Document.buyer_financials_id == BuyerFinancials.id,
            )
            .outerjoin(
                BuyerProfile,
                BuyerFinancials.buyer_id == BuyerProfile.id,
            )
            .outerjoin(
                BusinessFinancials,
                Document.business_financials_id == BusinessFinancials.id,
            )
            .outerjoin(
                Business,
                BusinessFinancials.business_id == Business.id,
            )
            .outerjoin(
                SellerProfile,
                Business.seller_id == SellerProfile.id,
            )
            .where(
                Document.id == document_id,
                or_(
                    BuyerProfile.user_id == user_id,
                    SellerProfile.user_id == user_id,
                ),
            )
        )
        if document is None:
            raise ResourceNotFoundError("Document not found")
        return document

    def get_document(self, document_id: UUID) -> Document | None:
        return self.session.scalar(
            select(Document).where(Document.id == document_id)
        )

    def get_expected_business_names(self, document: Document) -> list[str] | None:
        if document.business_financials_id is None:
            return None
        row = self.session.execute(
            select(Business.legal_name, Business.dba)
            .join(
                BusinessFinancials,
                BusinessFinancials.business_id == Business.id,
            )
            .where(
                BusinessFinancials.id == document.business_financials_id
            )
        ).one_or_none()
        if row is None:
            raise ResourceNotFoundError("Document business not found")
        return [name for name in row if name]

    def add_document(self, document: Document) -> Document:
        self.session.add(document)
        self.session.flush()
        return document

    def add_declaration(self, declaration: Declaration) -> Declaration:
        self.session.add(declaration)
        self.session.flush()
        return declaration

    def update_document_status(
        self,
        document: Document,
        status: VerificationStatus,
        *,
        provider: str | None = None,
        metadata: dict[str, Any] | None = None,
        verified_at: datetime | None = None,
    ) -> Document:
        document.verification_status = status
        if provider is not None:
            document.verification_provider = provider
        if metadata is not None:
            document.document_metadata = {
                **(document.document_metadata or {}),
                **metadata,
            }
        document.verified_at = verified_at
        self.session.flush()
        return document

    def create_document_uploaded_event(
        self,
        document: Document,
        user_id: UUID,
    ) -> UUID:
        event = OutboxRepository(self.session).create_event(
            OutboxEventCreate(
                idempotency_key=f"document_uploaded:{document.id}",
                event_type=EventType.DOCUMENT_UPLOADED,
                entity_type="document",
                entity_id=document.id,
                payload={
                    "user_id": str(user_id),
                    "document_id": str(document.id),
                },
            )
        )
        return event.id

    def get_document_owner_user_id(self, document: Document) -> UUID:
        if document.buyer_financials_id is not None:
            user_id = self.session.scalar(
                select(BuyerProfile.user_id)
                .join(
                    BuyerFinancials,
                    BuyerFinancials.buyer_id == BuyerProfile.id,
                )
                .where(BuyerFinancials.id == document.buyer_financials_id)
            )
        else:
            user_id = self.session.scalar(
                select(SellerProfile.user_id)
                .join(Business, Business.seller_id == SellerProfile.id)
                .join(
                    BusinessFinancials,
                    BusinessFinancials.business_id == Business.id,
                )
                .where(
                    BusinessFinancials.id == document.business_financials_id
                )
            )
        if user_id is None:
            raise ResourceNotFoundError("Document owner not found")
        return user_id

    def create_verification_completed_event(self, document: Document) -> UUID:
        user_id = self.get_document_owner_user_id(document)
        event = OutboxRepository(self.session).create_event(
            OutboxEventCreate(
                idempotency_key=f"verification_completed:document:{document.id}",
                event_type=EventType.VERIFICATION_COMPLETED,
                entity_type="document",
                entity_id=document.id,
                payload={
                    "user_id": str(user_id),
                    "verification_id": str(document.id),
                    "verification_domain": "document",
                },
            )
        )
        return event.id

    def get_user_by_provider_reference(self, reference: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.provider_reference == reference)
        )

    def get_business(self, business_id: UUID) -> Business | None:
        return self.session.scalar(
            select(Business).where(Business.id == business_id)
        )

    def get_business_financials_for_business(
        self,
        business_id: UUID,
    ) -> BusinessFinancials | None:
        return self.session.scalar(
            select(BusinessFinancials).where(
                BusinessFinancials.business_id == business_id
            )
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
