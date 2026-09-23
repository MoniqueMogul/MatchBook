from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.db_enum import DocumentType, VerificationStatus


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeStorage:
    bucket_name = "test-private"

    def __init__(self) -> None:
        self.presign_calls: list[tuple[str, str]] = []
        self.exists = True
        self.data = b"pdf"
        self.get_error: Exception | None = None

    def presign_upload(self, object_key: str, content_type: str):
        self.presign_calls.append((object_key, content_type))
        return "https://upload.invalid/signed", 900

    def object_exists(self, object_key: str) -> bool:
        return self.exists

    def get_bytes(self, object_key: str) -> bytes:
        if self.get_error:
            raise self.get_error
        return self.data


@pytest.fixture
def document():
    return SimpleNamespace(
        id=uuid4(),
        object_key=f"documents/{uuid4()}.pdf",
        bucket_name="test-private",
        document_type=DocumentType.PROFIT_AND_LOSS,
        verification_status=VerificationStatus.UPLOADED,
        verification_provider=None,
        verified_at=None,
        document_metadata={},
        buyer_financials_id=uuid4(),
        business_financials_id=None,
    )
