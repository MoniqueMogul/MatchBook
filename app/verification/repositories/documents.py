from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import VerificationStatus
from app.db.db_model import Document


def create(db: Session, **fields) -> Document:
    document = Document(**fields)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_by_id(db: Session, document_id: UUID) -> Optional[Document]:
    return db.query(Document).filter(Document.id == document_id).one_or_none()


def get_by_object_key(db: Session, object_key: str) -> Optional[Document]:
    return db.query(Document).filter(Document.object_key == object_key).one_or_none()


def list_for_business_financials(db: Session, business_financials_id: UUID) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.business_financials_id == business_financials_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


def list_for_buyer_financials(db: Session, buyer_financials_id: UUID) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.buyer_financials_id == buyer_financials_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


def update_status(
    db: Session,
    document_id: UUID,
    status: VerificationStatus,
    metadata: Optional[dict] = None,
) -> Optional[Document]:
    document = get_by_id(db, document_id)
    if document is None:
        return None
    document.verification_status = status
    if metadata is not None:
        document.document_metadata = {**(document.document_metadata or {}), **metadata}
    db.commit()
    db.refresh(document)
    return document