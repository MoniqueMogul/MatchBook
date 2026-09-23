import io
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.db.db_enum import DocumentType, VerificationStatus
from app.verification.exceptions import DocumentExtractionError, ProviderError
from app.verification.schemas import DetectedDocumentClassification
from app.verification import tasks
from app.verification.document_processing import extract_pdf_text
from tests.verification.conftest import FakeSession, FakeStorage


class FakeRepository:
    def __init__(self, document):
        self.document = document
        self.transitions = []

    def get_document(self, document_id):
        return self.document

    def update_document_status(
        self,
        document,
        status,
        *,
        provider=None,
        metadata=None,
        verified_at=None,
    ):
        document.verification_status = status
        if provider is not None:
            document.verification_provider = provider
        if metadata:
            document.document_metadata.update(metadata)
        document.verified_at = verified_at
        self.transitions.append(status)
        return document

    def create_verification_completed_event(self, document):
        self.completed_event_document = document


class Classifier:
    def __init__(self, detected, confidence):
        self.result = DetectedDocumentClassification(
            detected_type=detected,
            confidence=confidence,
        )

    def classify(self, text):
        return self.result


def test_pdf_parser_accepts_a_valid_image_only_pdf():
    from pypdf import PdfWriter

    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)

    assert extract_pdf_text(output.getvalue()) == ""


def test_pdf_parser_rejects_corrupt_pdf():
    with pytest.raises(DocumentExtractionError):
        extract_pdf_text(b"not a pdf")


def run(monkeypatch, document, classifier, storage=None, extractor=None):
    session = FakeSession()
    repository = FakeRepository(document)
    monkeypatch.setattr(tasks, "VerificationRepository", lambda _: repository)
    monkeypatch.setattr(
        tasks,
        "extract_pdf_text",
        extractor or (lambda _: "useful financial document text"),
    )
    result = tasks.run_document_processing(
        session=session,
        document_id=document.id,
        storage=storage or FakeStorage(),
        classifier=classifier,
        confidence_threshold=0.8,
    )
    return result, session, repository


def test_correct_document_type_becomes_verified(monkeypatch, document):
    result, _, repository = run(
        monkeypatch,
        document,
        Classifier(DocumentType.PROFIT_AND_LOSS, 0.94),
    )
    assert result == VerificationStatus.VERIFIED
    assert repository.transitions == [
        VerificationStatus.PROCESSING,
        VerificationStatus.VERIFIED,
    ]
    assert document.verified_at is not None
    assert document.verification_provider == "openai"
    assert document.document_metadata["matches_expected"] is True
    assert repository.completed_event_document is document


def test_detected_type_mismatch_requires_review(monkeypatch, document):
    result, _, repository = run(
        monkeypatch,
        document,
        Classifier(DocumentType.BANK_STATEMENT, 0.99),
    )
    assert result == VerificationStatus.REQUIRES_REVIEW
    assert document.document_metadata["reason_code"] == "document_type_mismatch"
    assert document.document_metadata["matches_expected"] is False
    assert not hasattr(repository, "completed_event_document")


def test_low_confidence_requires_review(monkeypatch, document):
    result, _, _ = run(
        monkeypatch,
        document,
        Classifier(DocumentType.PROFIT_AND_LOSS, 0.79),
    )
    assert result == VerificationStatus.REQUIRES_REVIEW
    assert document.document_metadata["reason_code"] == "low_confidence"


@pytest.mark.parametrize(
    "payload",
    [
        {"detected_type": "invented", "confidence": 0.9},
        {"detected_type": "tax_return", "confidence": 4},
        {"detected_type": "tax_return", "confidence": 0.9, "match": True},
    ],
)
def test_invalid_classifier_output_is_rejected(payload):
    with pytest.raises(ValidationError):
        DetectedDocumentClassification.model_validate(payload)


@pytest.mark.parametrize(
    ("failure", "extractor", "expected_code"),
    [
        (ProviderError("malformed"), None, "provider_failed"),
        (ProviderError("provider unavailable"), None, "provider_failed"),
        (
            None,
            lambda _: (_ for _ in ()).throw(DocumentExtractionError("bad")),
            "text_extraction_failed",
        ),
    ],
)
def test_controlled_processing_failures_end_in_failed(
    monkeypatch,
    document,
    failure,
    extractor,
    expected_code,
):
    classifier = MagicMock()
    if failure:
        classifier.classify.side_effect = failure
    result, session, repository = run(
        monkeypatch,
        document,
        classifier,
        extractor=extractor,
    )
    assert result == VerificationStatus.FAILED
    assert repository.transitions[-1] == VerificationStatus.FAILED
    assert document.verification_status != VerificationStatus.PROCESSING
    assert document.document_metadata["failure_code"] == expected_code
    assert session.rollbacks == 1


def test_r2_retrieval_failure_ends_in_failed(monkeypatch, document):
    storage = FakeStorage()
    storage.get_error = ProviderError("R2 unavailable")
    result, _, repository = run(
        monkeypatch,
        document,
        Classifier(DocumentType.PROFIT_AND_LOSS, 0.9),
        storage=storage,
    )
    assert result == VerificationStatus.FAILED
    assert repository.transitions[-1] == VerificationStatus.FAILED


def test_image_only_pdf_requires_review_without_calling_model(monkeypatch, document):
    classifier = MagicMock()
    result, _, _ = run(
        monkeypatch,
        document,
        classifier,
        extractor=lambda _: "",
    )
    assert result == VerificationStatus.REQUIRES_REVIEW
    assert document.document_metadata["reason_code"] == "no_extractable_text"
    classifier.classify.assert_not_called()


def test_classifier_input_is_bounded(monkeypatch, document):
    classifier = Classifier(DocumentType.PROFIT_AND_LOSS, 0.9)
    classifier.classify = MagicMock(return_value=classifier.result)
    session = FakeSession()
    repository = FakeRepository(document)
    monkeypatch.setattr(tasks, "VerificationRepository", lambda _: repository)
    monkeypatch.setattr(tasks, "extract_pdf_text", lambda _: "x" * 100)

    tasks.run_document_processing(
        session=session,
        document_id=document.id,
        storage=FakeStorage(),
        classifier=classifier,
        confidence_threshold=0.8,
        max_classifier_characters=25,
    )

    classifier.classify.assert_called_once_with("x" * 25)


def test_oversized_download_fails_before_extraction(monkeypatch, document):
    storage = FakeStorage()
    storage.data = b"x" * 11
    extractor = MagicMock(return_value="text")
    session = FakeSession()
    repository = FakeRepository(document)
    monkeypatch.setattr(tasks, "VerificationRepository", lambda _: repository)
    monkeypatch.setattr(tasks, "extract_pdf_text", extractor)
    result = tasks.run_document_processing(
        session=session,
        document_id=document.id,
        storage=storage,
        classifier=Classifier(DocumentType.PROFIT_AND_LOSS, 0.9),
        confidence_threshold=0.8,
        max_document_bytes=10,
    )
    assert result == VerificationStatus.FAILED
    assert document.verification_status == VerificationStatus.FAILED
    extractor.assert_not_called()
