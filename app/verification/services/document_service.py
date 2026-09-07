import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import DeclarationStatus, VerificationStatus
from app.db.db_model import NDA, Declaration
from app.verification.integrations import storage
from app.verification.repositories import documents as documents_repo
from app.verification.schemas.document import DocumentUploadRequest, DocumentUploadResponse
from app.verification.tasks.document_tasks import process_document_task


def initiate_upload(db: Session, request: DocumentUploadRequest) -> DocumentUploadResponse:
    object_key = f"documents/{uuid.uuid4()}/{request.original_filename}"
    bucket_name = storage.DEFAULT_BUCKET

    document = documents_repo.create(
        db,
        document_type=request.document_type,
        original_filename=request.original_filename,
        mime_type=request.mime_type,
        file_size=request.file_size,
        storage_provider="cloudflare_r2",
        bucket_name=bucket_name,
        object_key=object_key,
        verification_status=VerificationStatus.UPLOADING,
        buyer_financials_id=request.buyer_financials_id,
        business_financials_id=request.business_financials_id,
    )

    if request.declaration_signed:
        if document.business_financials_id is None:
            raise ValueError("Authenticity declaration requires a business financials document")
        declaration = Declaration(
            business_financials_id=document.business_financials_id,
            document_id=document.id,
            status=DeclarationStatus.SIGNED,
            version="1",
            seller_signed_at=datetime.utcnow(),
        )
        db.add(declaration)
        db.commit()
        db.refresh(declaration)

    if request.nda_id is not None:
        nda = db.query(NDA).filter(NDA.id == request.nda_id).one_or_none()
        if nda is None:
            raise ValueError(f"NDA not found: {request.nda_id}")
        nda.document_id = document.id
        db.commit()

    upload_url = storage.get_presigned_upload_url(
        bucket_name=bucket_name, object_key=object_key, content_type=request.mime_type
    )

    return DocumentUploadResponse(
        document_id=document.id, upload_url=upload_url, object_key=object_key
    )


def confirm_upload(db: Session, document_id: UUID) -> None:
    document = documents_repo.get_by_id(db, document_id)
    if document is None:
        raise ValueError(f"Document not found: {document_id}")
    if document.declaration is None or document.declaration.status != DeclarationStatus.SIGNED:
        raise ValueError("Cannot process document without signed authenticity declaration")

    documents_repo.update_status(db, document_id, VerificationStatus.UPLOADED)
    process_document_task(document_id=str(document_id))