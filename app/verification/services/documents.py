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
from app.verification.schemas import (
    DocumentUploadRequest,
    DocumentUploadResponse, DocumentDownloadResponse,
)


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
        self.dispatch_document = (
            dispatch_document or _dispatch_document
        )
        self.dispatch_outbox = (
            dispatch_outbox or _dispatch_outbox
        )

    # ============================================================
    # BUYER DOCUMENTS
    # ============================================================

    def initiate_buyer_upload(
        self,
        request: DocumentUploadRequest,
        user_id: UUID,
    ) -> DocumentUploadResponse:
        """
        Initiate a document upload for the authenticated buyer.

        The client does not supply buyer_financials_id.

        The service resolves the authenticated user's BuyerProfile,
        then gets or creates the internal BuyerFinancials container.
        """

        self._validate_upload(
            request,
            is_business_document=False,
        )

        buyer = self.repository.require_buyer_profile(
            user_id
        )

        try:
            financials = (
                self.repository.get_or_create_buyer_financials(
                    buyer.id
                )
            )

            return self._create_upload(
                request=request,
                buyer_financials_id=financials.id,
            )

        except Exception:
            self.session.rollback()
            raise

    def list_buyer_documents(
        self,
        user_id: UUID,
    ) -> list[Document]:
        """
        Return document metadata for the authenticated buyer.

        This is intentionally read-only.

        The BuyerProfile must exist because it represents the
        authenticated buyer domain identity.

        If BuyerFinancials does not exist yet, return an empty list
        instead of creating database state during a GET request.
        """

        buyer = self.repository.require_buyer_profile(
            user_id
        )

        financials = (
            self.repository.get_buyer_financials_for_buyer(
                buyer.id
            )
        )

        if financials is None:
            return []

        return (
            self.repository.list_documents_for_buyer_financials(
                financials.id
            )
        )

    # ============================================================
    # BUSINESS DOCUMENTS
    # ============================================================

    def initiate_business_upload(
        self,
        business_id: UUID,
        request: DocumentUploadRequest,
        user_id: UUID,
    ) -> DocumentUploadResponse:
        """
        Initiate a document upload for one of the authenticated
        seller's businesses.

        The client supplies only the public business_id through
        the route.

        The service verifies ownership and gets or creates the
        internal BusinessFinancials container.
        """

        self._validate_upload(
            request,
            is_business_document=True,
        )

        business = self.repository.require_owned_business(
            business_id,
            user_id,
        )

        try:
            financials = (
                self.repository.get_or_create_business_financials(
                    business.id
                )
            )

            return self._create_upload(
                request=request,
                business_financials_id=financials.id,
            )

        except Exception:
            self.session.rollback()
            raise

    def list_business_documents(
        self,
        business_id: UUID,
        user_id: UUID,
    ) -> list[Document]:
        """
        Return document metadata for an owned business.

        This is intentionally read-only.

        If BusinessFinancials does not exist yet, return an empty
        list instead of creating database state during a GET request.
        """

        business = self.repository.require_owned_business(
            business_id,
            user_id,
        )

        financials = (
            self.repository.get_business_financials_for_business(
                business.id
            )
        )

        if financials is None:
            return []

        return (
            self.repository.list_documents_for_business_financials(
                financials.id
            )
        )

    # ============================================================
    # SHARED DOCUMENT OPERATIONS
    # ============================================================

    def get_owned_document(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> Document:
        return self.repository.require_owned_document(
            document_id,
            user_id,
        )

    def confirm_upload(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> Document:
        document = self.repository.require_owned_document(
            document_id,
            user_id,
        )

        if (
            document.verification_status
            == VerificationStatus.UPLOADING
        ):
            if not self.storage.object_exists(
                document.object_key
            ):
                raise InvalidVerificationRequest(
                    "Uploaded object was not found"
                )

            try:
                self.repository.update_document_status(
                    document,
                    VerificationStatus.UPLOADED,
                )

                event_id = (
                    self.repository.create_document_uploaded_event(
                        document,
                        user_id,
                    )
                )

                self.session.commit()

            except Exception:
                self.session.rollback()
                raise

            self.dispatch_outbox(
                str(event_id)
            )

        elif (
            document.verification_status
            != VerificationStatus.UPLOADED
        ):
            raise InvalidVerificationRequest(
                "Only uploading or uploaded documents "
                "can be confirmed"
            )

        self.dispatch_document(
            str(document.id)
        )

        return document

    def trigger_verification(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> Document:
        document = self.repository.require_owned_document(
            document_id,
            user_id,
        )

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
                    metadata={
                        "retry_requested": True,
                    },
                )

                self.session.commit()

            except Exception:
                self.session.rollback()
                raise

        self.dispatch_document(
            str(document.id)
        )

        return document

    def create_download_url(
            self,
            document_id: UUID,
            user_id: UUID,
    ) -> DocumentDownloadResponse:
        document = self.repository.require_owned_document(
            document_id,
            user_id,
        )

        download_url, expires = (
            self.storage.presign_download(
                document.object_key
            )
        )

        return DocumentDownloadResponse(
            download_url=download_url,
            expires_in_seconds=expires,
        )

    # ============================================================
    # INTERNAL UPLOAD CREATION
    # ============================================================

    def _create_upload(
        self,
        *,
        request: DocumentUploadRequest,
        buyer_financials_id: UUID | None = None,
        business_financials_id: UUID | None = None,
    ) -> DocumentUploadResponse:
        """
        Create the internal Document row and temporary R2 upload URL.

        Financial IDs are resolved internally by the service.
        They never come from DocumentUploadRequest.
        """

        owner_count = sum(
            value is not None
            for value in (
                buyer_financials_id,
                business_financials_id,
            )
        )

        if owner_count != 1:
            raise RuntimeError(
                "Document upload requires exactly one "
                "resolved financial owner"
            )

        document_id = uuid4()

        object_key = (
            f"documents/{document_id}.pdf"
        )

        upload_url, expires = (
            self.storage.presign_upload(
                object_key,
                SUPPORTED_MIME_TYPE,
            )
        )

        document = Document(
            id=document_id,
            buyer_financials_id=buyer_financials_id,
            business_financials_id=business_financials_id,
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
            self.repository.add_document(
                document
            )

            if business_financials_id is not None:
                self.repository.add_declaration(
                    Declaration(
                        business_financials_id=(
                            business_financials_id
                        ),
                        document_id=document.id,
                        status=DeclarationStatus.SIGNED,
                        version="1",
                        seller_signed_at=datetime.now(
                            timezone.utc
                        ),
                    )
                )

            self.session.commit()

        except Exception:
            self.session.rollback()
            raise

        return DocumentUploadResponse(
            document_id=document.id,
            upload_url=upload_url,
            required_headers={
                "Content-Type": SUPPORTED_MIME_TYPE,
            },
            expires_in_seconds=expires,
        )

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_upload(
        self,
        request: DocumentUploadRequest,
        *,
        is_business_document: bool,
    ) -> None:
        if request.mime_type != SUPPORTED_MIME_TYPE:
            raise InvalidVerificationRequest(
                f"Unsupported MIME type; only "
                f"{SUPPORTED_MIME_TYPE} is accepted"
            )

        if (
            request.file_size
            > self.settings.max_document_bytes
        ):
            raise InvalidVerificationRequest(
                "Document exceeds the size limit"
            )

        if (
            is_business_document
            and not request.declaration_signed
        ):
            raise InvalidVerificationRequest(
                "Business documents require a signed "
                "authenticity declaration"
            )

        if (
            not is_business_document
            and request.declaration_signed
        ):
            raise InvalidVerificationRequest(
                "Authenticity declarations apply only "
                "to business documents"
            )


def _dispatch_document(
    document_id: str,
) -> None:
    from app.verification.tasks import process_document

    process_document.delay(
        document_id
    )


def _dispatch_outbox(
    event_id: str,
) -> None:
    from app.events.tasks import send_outbox_event

    send_outbox_event.delay(
        event_id
    )