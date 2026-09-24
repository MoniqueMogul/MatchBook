import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.db_enum import VerificationStatus
from app.verification.exceptions import ProviderError, ResourceNotFoundError
from app.verification.integrations.plaid import eligible_depository_balance
from app.verification.services.plaid import PlaidService
from tests.verification.conftest import FakeSession


def make_service():
    session = FakeSession()
    provider = MagicMock()
    provider.create_link_token = AsyncMock()
    provider.exchange_public_token = AsyncMock()
    provider.get_balances = AsyncMock()
    service = PlaidService(session, provider)
    service.repository = MagicMock()
    return service, session, provider


def financials():
    return SimpleNamespace(
        id=uuid4(),
        verified_cash_amount=None,
        verification_status=VerificationStatus.UNVERIFIED,
        verification_provider=None,
        provider_reference=None,
        provider_response=None,
        verified_at=None,
    )


def test_mocked_link_token_path_enforces_buyer_ownership():
    service, _, provider = make_service()
    record = financials()
    service.repository.require_owned_buyer_financials.return_value = record
    provider.create_link_token.return_value = {
        "link_token": "link-sandbox",
        "expiration": "2026-09-23T12:00:00Z",
    }

    result = asyncio.run(service.create_link_token(record.id, uuid4()))

    assert result.link_token == "link-sandbox"
    service.repository.require_owned_buyer_financials.assert_called_once()
    provider.create_link_token.assert_awaited_once_with(str(record.id))


def test_unauthorized_buyer_makes_no_plaid_call():
    service, _, provider = make_service()
    service.repository.require_owned_buyer_financials.side_effect = (
        ResourceNotFoundError("Buyer financials not found")
    )
    with pytest.raises(ResourceNotFoundError):
        asyncio.run(service.create_link_token(uuid4(), uuid4()))
    provider.create_link_token.assert_not_awaited()


def test_plaid_status_read_enforces_buyer_ownership():
    service, _, _ = make_service()
    service.repository.require_owned_buyer_financials.side_effect = (
        ResourceNotFoundError("Buyer financials not found")
    )
    with pytest.raises(ResourceNotFoundError):
        service.get_status(uuid4(), uuid4())


def test_public_token_is_exchanged_transiently_and_balances_are_persisted():
    service, session, provider = make_service()
    record = financials()
    service.repository.require_owned_buyer_financials.return_value = record
    provider.exchange_public_token.return_value = {
        "access_token": "access-secret",
        "item_id": "item-safe-reference",
    }
    provider.get_balances.return_value = [
        {
            "type": "depository",
            "balances": {"available": 1250.50, "current": 1300},
        },
        {"type": "credit", "balances": {"current": 9000}},
        {
            "type": "depository",
            "balances": {"available": None, "current": 250},
        },
    ]

    result = asyncio.run(
        service.verify_funds(record.id, uuid4(), "public-ephemeral")
    )

    assert result.eligible_balance == 1500.5
    assert result.eligible_account_count == 2
    assert record.verified_cash_amount == Decimal("1500.50")
    assert record.provider_reference == "item-safe-reference"
    assert "access-secret" not in repr(record.__dict__)
    assert "public-ephemeral" not in repr(record.__dict__)
    assert session.commits == 2
    provider.get_balances.assert_awaited_once_with("access-secret")


def test_plaid_provider_failure_records_failed_without_secret():
    service, session, provider = make_service()
    record = financials()
    service.repository.require_owned_buyer_financials.return_value = record
    provider.exchange_public_token.side_effect = ProviderError("down")

    with pytest.raises(ProviderError):
        asyncio.run(service.verify_funds(record.id, uuid4(), "public-secret"))

    assert record.verification_status == VerificationStatus.FAILED
    assert record.provider_response == {"failure_code": "provider_failed"}
    assert "public-secret" not in repr(record.__dict__)
    assert session.rollbacks == 1


def test_eligible_balance_counts_only_positive_depository_funds():
    total, count = eligible_depository_balance(
        [
            {"type": "depository", "balances": {"available": 100}},
            {"type": "depository", "balances": {"available": -25}},
            {"type": "investment", "balances": {"available": 10000}},
        ]
    )
    assert total == Decimal("75")
    assert count == 2
