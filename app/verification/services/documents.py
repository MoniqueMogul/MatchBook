from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db.db_enum import (
    DeclarationStatus,
    StorageProvider,
    VerificationStatus,
)
from app.db.db_model import Declaration, Document
from app.verification.config import VerificationSettings
from app.verification.document_processing import SUPPORTED_MIME_TYPE
from app.verification.exceptions import InvalidVerificationRequest
from app.verification.integrations.storage import DocumentStorage
from app.verification.repositories import VerificationRepository
from app.verification.schemas import DocumentUploadRequest, DocumentUploadResponse


class DocumentService:
    def __init__(
        self,
        session: Session,
        storage: DocumentStorage,
        settings: VerificationSettings,
        *,
        dispatch_document: Callable[[str], None] | None = None,
        dispatch_outbox: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings
        self.repository = VerificationRepository(session)
        self.dispatch_document = dispatch_document or _dispatch_document
        self.dispatch_outbox = dispatch_outbox or _dispatch_outbox

    def initiate_upload(
        self,
        request: DocumentUploadRequest,
        user_id: UUID,
    ) -> DocumentUploadResponse:
        self._validate_upload(request)
        if request.buyer_financials_id is not None:
            self.repository.require_owned_buyer_financials(
                request.buyer_financials_id,
                user_id,
            )
        else:
            assert request.business_financials_id is not None
            self.repository.require_owned_business_financials(
                request.business_financials_id,
                user_id,
            )

        document_id = uuid4()
        object_key = f"documents/{document_id}.pdf"
        upload_url, expires = self.storage.presign_upload(
            object_key,
            SUPPORTED_MIME_TYPE,
        )
        document = Document(
            id=document_id,
            buyer_financials_id=request.buyer_financials_id,
            business_financials_id=request.business_financials_id,
            document_type=request.expected_document_type,
            original_filename=request.original_filename,
            mime_type=request.mime_type,
            file_size=request.file_size,
            storage_provider=StorageProvider.CLOUDFLARE_R2,
            bucket_name=self.storage.bucket_name,
            object_key=object_key,
            verification_status=VerificationStatus.UPLOADING,
            document_metadata={
                "expected_type_source": "upload_request",
                "classification_version": 1,
            },
        )
        try:
            self.repository.add_document(document)
            if request.business_financials_id is not None:
                self.repository.add_declaration(
                    Declaration(
                        business_financials_id=request.business_financials_id,
                        document_id=document.id,
                        status=DeclarationStatus.SIGNED,
                        version="1",
                        seller_signed_at=datetime.now(timezone.utc),
                    )
                )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        return DocumentUploadResponse(
            document_id=document.id,
            upload_url=upload_url,
            required_headers={"Content-Type": SUPPORTED_MIME_TYPE},
            expires_in_seconds=expires,
        )

    def get_owned_document(self, document_id: UUID, user_id: UUID) -> Document:
        return self.repository.require_owned_document(document_id, user_id)

    def list_owned_documents(
        self,
        user_id: UUID,
        *,
        buyer_financials_id: UUID | None = None,
        business_financials_id: UUID | None = None,
    ) -> list[Document]:
        if (buyer_financials_id is None) == (business_financials_id is None):
            raise InvalidVerificationRequest(
                "Exactly one financials ID must be supplied"
            )

        if buyer_financials_id is not None:
            self.repository.require_owned_buyer_financials(
                buyer_financials_id,
                user_id,
            )
            return self.repository.list_documents_for_buyer_financials(
                buyer_financials_id
            )

        assert business_financials_id is not None
        self.repository.require_owned_business_financials(
            business_financials_id,
            user_id,
        )
        return self.repository.list_documents_for_business_financials(
            business_financials_id
        )

    def confirm_upload(self, document_id: UUID, user_id: UUID) -> Document:
        document = self.repository.require_owned_document(document_id, user_id)
        if document.verification_status == VerificationStatus.UPLOADING:
            if not self.storage.object_exists(document.object_key):
                raise InvalidVerificationRequest("Uploaded object was not found")
            try:
                self.repository.update_document_status(
                    document,
                    VerificationStatus.UPLOADED,
                )
                event_id = self.repository.create_document_uploaded_event(
                    document,
                    user_id,
                )
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
            self.dispatch_outbox(str(event_id))
        elif document.verification_status != VerificationStatus.UPLOADED:
            raise InvalidVerificationRequest(
                "Only uploading or uploaded documents can be confirmed"
            )
        self.dispatch_document(str(document.id))
        return document

    def trigger_verification(self, document_id: UUID, user_id: UUID) -> Document:
        document = self.repository.require_owned_document(document_id, user_id)
        allowed = {
            VerificationStatus.UPLOADED,
            VerificationStatus.PROCESSING,
            VerificationStatus.REQUIRES_REVIEW,
            VerificationStatus.FAILED,
        }
        if document.verification_status not in allowed:
            raise InvalidVerificationRequest(
                "Document is not ready for verification"
            )
        if document.verification_status in {
            VerificationStatus.REQUIRES_REVIEW,
            VerificationStatus.FAILED,
        }:
            try:
                self.repository.update_document_status(
                    document,
                    VerificationStatus.UPLOADED,
                    metadata={"retry_requested": True},
                )
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        self.dispatch_document(str(document.id))
        return document

    def _validate_upload(self, request: DocumentUploadRequest) -> None:
        if request.mime_type != SUPPORTED_MIME_TYPE:
            raise InvalidVerificationRequest(
                f"Unsupported MIME type; only {SUPPORTED_MIME_TYPE} is accepted"
            )
        if request.file_size > self.settings.max_document_bytes:
            raise InvalidVerificationRequest("Document exceeds the size limit")
        if request.business_financials_id is not None and not request.declaration_signed:
            raise InvalidVerificationRequest(
                "Business documents require a signed authenticity declaration"
            )
        if request.buyer_financials_id is not None and request.declaration_signed:
            raise InvalidVerificationRequest(
                "Authenticity declarations apply only to business documents"
            )


def _dispatch_document(document_id: str) -> None:
    from app.verification.tasks import process_document

    process_document.delay(document_id)


def _dispatch_outbox(event_id: str) -> None:
    from app.events.tasks import send_outbox_event

    send_outbox_event.delay(event_id)
