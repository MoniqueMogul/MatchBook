from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.db.db_enum import DocumentType, VerificationStatus
from app.verification.config import VerificationSettings
from app.verification.exceptions import (
    InvalidVerificationRequest,
    ResourceNotFoundError,
)
from app.verification.schemas import DocumentUploadRequest
from app.verification.services.documents import DocumentService
from tests.verification.conftest import FakeSession, FakeStorage


def make_service():
    session = FakeSession()
    storage = FakeStorage()
    dispatched: list[str] = []
    outbox_dispatched: list[str] = []
    service = DocumentService(
        session,
        storage,
        VerificationSettings(),
        dispatch_document=dispatched.append,
        dispatch_outbox=outbox_dispatched.append,
    )
    service.repository = MagicMock()
    return service, session, storage, dispatched, outbox_dispatched


def buyer_request(**overrides):
    values = {
        "expected_document_type": DocumentType.BANK_STATEMENT,
        "original_filename": "statement.pdf",
        "mime_type": "application/pdf",
        "file_size": 1024,
        "buyer_financials_id": uuid4(),
    }
    values.update(overrides)
    return DocumentUploadRequest(**values)


def business_request(**overrides):
    values = {
        "expected_document_type": DocumentType.TAX_RETURN,
        "original_filename": "tax return.pdf",
        "mime_type": "application/pdf",
        "file_size": 2048,
        "business_financials_id": uuid4(),
        "declaration_signed": True,
    }
    values.update(overrides)
    return DocumentUploadRequest(**values)


def test_authorized_owner_can_initiate_buyer_upload():
    service, session, storage, _, _ = make_service()
    request = buyer_request()

    result = service.initiate_upload(request, uuid4())

    service.repository.require_owned_buyer_financials.assert_called_once()
    created = service.repository.add_document.call_args.args[0]
    assert created.verification_status == VerificationStatus.UPLOADING
    assert created.document_type == DocumentType.BANK_STATEMENT
    assert created.object_key.endswith(".pdf")
    assert request.original_filename not in created.object_key
    assert result.required_headers == {"Content-Type": "application/pdf"}
    assert storage.presign_calls
    assert session.commits == 1


def test_authorized_owner_can_initiate_business_upload_with_declaration():
    service, session, _, _, _ = make_service()
    request = business_request()

    service.initiate_upload(request, uuid4())

    service.repository.require_owned_business_financials.assert_called_once()
    service.repository.add_declaration.assert_called_once()
    assert session.commits == 1


@pytest.mark.parametrize("owner_kind", ["buyer", "business"])
def test_unauthorized_user_cannot_initiate_for_other_financials(owner_kind):
    service, session, storage, _, _ = make_service()
    method = (
        service.repository.require_owned_buyer_financials
        if owner_kind == "buyer"
        else service.repository.require_owned_business_financials
    )
    method.side_effect = ResourceNotFoundError("not found")
    request = buyer_request() if owner_kind == "buyer" else business_request()

    with pytest.raises(ResourceNotFoundError):
        service.initiate_upload(request, uuid4())

    assert not storage.presign_calls
    assert session.commits == 0


def test_unsupported_mime_is_rejected_before_storage_or_persistence():
    service, session, storage, _, _ = make_service()
    request = buyer_request(mime_type="image/png")

    with pytest.raises(InvalidVerificationRequest, match="only application/pdf"):
        service.initiate_upload(request, uuid4())

    assert not storage.presign_calls
    assert session.commits == 0


def test_business_document_requires_declaration():
    service, _, _, _, _ = make_service()
    with pytest.raises(InvalidVerificationRequest, match="signed"):
        service.initiate_upload(
            business_request(declaration_signed=False),
            uuid4(),
        )


def test_unauthorized_user_cannot_read_document():
    service, _, _, _, _ = make_service()
    service.repository.require_owned_document.side_effect = ResourceNotFoundError(
        "Document not found"
    )
    with pytest.raises(ResourceNotFoundError):
        service.get_owned_document(uuid4(), uuid4())


def test_owner_can_list_buyer_documents_after_authorization():
    service, _, _, _, _ = make_service()
    user_id, financials_id = uuid4(), uuid4()
    documents = [object(), object()]
    service.repository.list_documents_for_buyer_financials.return_value = documents

    result = service.list_owned_documents(
        user_id,
        buyer_financials_id=financials_id,
    )

    assert result == documents
    service.repository.require_owned_buyer_financials.assert_called_once_with(
        financials_id,
        user_id,
    )
    service.repository.list_documents_for_buyer_financials.assert_called_once_with(
        financials_id
    )


def test_owner_can_list_business_documents_after_authorization():
    service, _, _, _, _ = make_service()
    user_id, financials_id = uuid4(), uuid4()
    documents = [object()]
    service.repository.list_documents_for_business_financials.return_value = documents

    result = service.list_owned_documents(
        user_id,
        business_financials_id=financials_id,
    )

    assert result == documents
    service.repository.require_owned_business_financials.assert_called_once_with(
        financials_id,
        user_id,
    )
    service.repository.list_documents_for_business_financials.assert_called_once_with(
        financials_id
    )


@pytest.mark.parametrize("owner_kind", ["buyer", "business"])
def test_another_user_cannot_list_financial_documents(owner_kind):
    service, _, _, _, _ = make_service()
    financials_id = uuid4()
    ownership_check = (
        service.repository.require_owned_buyer_financials
        if owner_kind == "buyer"
        else service.repository.require_owned_business_financials
    )
    list_documents = (
        service.repository.list_documents_for_buyer_financials
        if owner_kind == "buyer"
        else service.repository.list_documents_for_business_financials
    )
    ownership_check.side_effect = ResourceNotFoundError("not found")
    scope = {f"{owner_kind}_financials_id": financials_id}

    with pytest.raises(ResourceNotFoundError):
        service.list_owned_documents(uuid4(), **scope)

    list_documents.assert_not_called()


@pytest.mark.parametrize(
    "scope",
    [{}, {"buyer_financials_id": uuid4(), "business_financials_id": uuid4()}],
)
def test_document_list_requires_exactly_one_scope(scope):
    service, _, _, _, _ = make_service()

    with pytest.raises(InvalidVerificationRequest):
        service.list_owned_documents(uuid4(), **scope)

    service.repository.require_owned_buyer_financials.assert_not_called()
    service.repository.require_owned_business_financials.assert_not_called()


def test_empty_owned_document_collection_returns_empty_list():
    service, _, _, _, _ = make_service()
    service.repository.list_documents_for_buyer_financials.return_value = []

    assert service.list_owned_documents(
        uuid4(), buyer_financials_id=uuid4()
    ) == []


def test_document_query_orders_by_uploaded_at_then_id_descending():
    from unittest.mock import MagicMock

    from app.verification.repositories import VerificationRepository

    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    repository = VerificationRepository(session)

    repository.list_documents_for_buyer_financials(uuid4())
    statement = session.scalars.call_args.args[0]
    order = statement._order_by_clauses

    assert len(order) == 2
    assert str(order[0]) == "documents.uploaded_at DESC"
    assert str(order[1]) == "documents.id DESC"
    repository.list_documents_for_business_financials(uuid4())
    business_statement = session.scalars.call_args.args[0]
    business_order = business_statement._order_by_clauses
    assert str(business_order[0]) == "documents.uploaded_at DESC"
    assert str(business_order[1]) == "documents.id DESC"


def test_owned_business_with_no_documents_returns_empty_list():
    service, _, _, _, _ = make_service()
    service.repository.list_documents_for_business_financials.return_value = []

    assert service.list_owned_documents(
        uuid4(), business_financials_id=uuid4()
    ) == []


def test_existing_get_owned_document_remains_available(document):
    service, _, _, _, _ = make_service()
    user_id = uuid4()
    service.repository.require_owned_document.return_value = document

    assert service.get_owned_document(document.id, user_id) is document
    service.repository.require_owned_document.assert_called_once_with(
        document.id,
        user_id,
    )


def test_unauthorized_user_cannot_confirm_document():
    service, _, _, dispatched, _ = make_service()
    service.repository.require_owned_document.side_effect = ResourceNotFoundError(
        "Document not found"
    )
    with pytest.raises(ResourceNotFoundError):
        service.confirm_upload(uuid4(), uuid4())
    assert not dispatched


def test_confirm_checks_object_persists_event_then_dispatches(document):
    service, session, storage, dispatched, outbox_dispatched = make_service()
    document.verification_status = VerificationStatus.UPLOADING
    service.repository.require_owned_document.return_value = document
    event_id = uuid4()
    service.repository.create_document_uploaded_event.return_value = event_id

    service.confirm_upload(document.id, uuid4())

    service.repository.update_document_status.assert_called_once_with(
        document,
        VerificationStatus.UPLOADED,
    )
    assert session.commits == 1
    assert outbox_dispatched == [str(event_id)]
    assert dispatched == [str(document.id)]


def test_confirm_rejects_missing_r2_object(document):
    service, session, storage, dispatched, _ = make_service()
    service.repository.require_owned_document.return_value = document
    document.verification_status = VerificationStatus.UPLOADING
    storage.exists = False

    with pytest.raises(InvalidVerificationRequest, match="not found"):
        service.confirm_upload(document.id, uuid4())

    assert session.commits == 0
    assert not dispatched


def test_unauthorized_user_cannot_trigger_verification():
    service, _, _, dispatched, _ = make_service()
    service.repository.require_owned_document.side_effect = ResourceNotFoundError(
        "Document not found"
    )
    with pytest.raises(ResourceNotFoundError):
        service.trigger_verification(uuid4(), uuid4())
    assert not dispatched
