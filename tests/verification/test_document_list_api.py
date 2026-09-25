from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Route tests replace authenticated identity; no Supabase provider is needed.
fake_auth_module = ModuleType("app.auth.auth")
fake_auth_module.supabase = MagicMock()
sys.modules.setdefault("app.auth.auth", fake_auth_module)

from app.auth.dependencies import get_current_user_id
from app.db.session import get_db
from app.verification.routes import documents as document_routes
from app.verification.exceptions import InvalidVerificationRequest
from app.verification.schemas import DocumentResponse


def response_document():
    return SimpleNamespace(
        id=uuid4(),
        document_type="profit_and_loss",
        original_filename="income.pdf",
        mime_type="application/pdf",
        file_size=1024,
        verification_status="verified",
        verification_provider="mock",
        verified_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        document_metadata={"classification_version": 1},
        uploaded_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        bucket_name="private-bucket",
        object_key="private/path.pdf",
    )


def client_for(monkeypatch, documents, *, user_id=None):
    authenticated_user_id = user_id or uuid4()

    def list_owned_documents(current_user_id, **scope):
        if (scope.get("buyer_financials_id") is None) == (
            scope.get("business_financials_id") is None
        ):
            raise InvalidVerificationRequest(
                "Exactly one financials ID must be supplied"
            )
        return documents

    service = SimpleNamespace(
        list_owned_documents=list_owned_documents,
        get_owned_document=lambda document_id, current_user_id: documents[0],
    )
    monkeypatch.setattr(document_routes, "_service", lambda db: service)
    app = FastAPI()
    app.include_router(document_routes.router, prefix="/verification")
    app.dependency_overrides[get_current_user_id] = lambda: authenticated_user_id
    app.dependency_overrides[get_db] = lambda: object()
    return TestClient(app)


def test_authenticated_buyer_document_list_uses_document_response(monkeypatch):
    document = response_document()
    client = client_for(monkeypatch, [document])

    response = client.get(
        "/verification/documents",
        params={"buyer_financials_id": str(uuid4())},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(document.id)
    assert response.json()[0]["original_filename"] == "income.pdf"
    assert set(response.json()[0]) == set(DocumentResponse.model_fields)
    assert "bucket_name" not in response.json()[0]
    assert "object_key" not in response.json()[0]


def test_business_document_list_and_empty_list_response(monkeypatch):
    client = client_for(monkeypatch, [])

    response = client.get(
        "/verification/documents",
        params={"business_financials_id": str(uuid4())},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_requires_exactly_one_scope(monkeypatch):
    client = client_for(monkeypatch, [])

    no_scope = client.get("/verification/documents")
    both_scopes = client.get(
        "/verification/documents",
        params={
            "buyer_financials_id": str(uuid4()),
            "business_financials_id": str(uuid4()),
        },
    )

    assert no_scope.status_code == 400
    assert both_scopes.status_code == 400


def test_existing_document_id_get_route_still_works(monkeypatch):
    document = response_document()
    client = client_for(monkeypatch, [document])

    response = client.get(f"/verification/documents/{document.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(document.id)
