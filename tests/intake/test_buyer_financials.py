from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.db_model import (
    BuyerFinancials,
    BuyerProfile,
)
from app.intake.repository import (
    IntakeNotFoundError,
    IntakeRepository,
)
from app.intake.routes import (
    get_buyer_financials,
    upsert_buyer_financials,
)
from app.intake.schemas.buyer_financials import (
    BuyerFinancialsUpsert,
)


def build_financials_result():
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=uuid4(),
        buyer_id=uuid4(),
        funding_source="all_cash",
        reported_cash_available=Decimal("250000.00"),
        verified_cash_amount=Decimal("200000.00"),
        financing_requested_amount=None,
        financing_approved_amount=None,
        lender_name=None,
        lender_approval_status="pending",
        verification_status="verified",
        verified_at=now,
        created_at=now,
        updated_at=now,
    )


def test_upsert_schema_accepts_empty_payload() -> None:
    payload = BuyerFinancialsUpsert()

    assert payload.model_dump(exclude_unset=True) == {}


def test_upsert_schema_rejects_provider_controlled_fields() -> None:
    with pytest.raises(ValidationError):
        BuyerFinancialsUpsert.model_validate(
            {
                "verification_status": "verified",
                "verified_cash_amount": 500000,
            }
        )


def test_repository_creates_financials_for_buyer() -> None:
    user_id = uuid4()
    buyer_id = uuid4()

    profile = BuyerProfile(
        id=buyer_id,
        user_id=user_id,
    )

    session = MagicMock(spec=Session)
    session.scalar.side_effect = [
        profile,
        None,
    ]

    repository = IntakeRepository(session)

    result = repository.upsert_buyer_financials(
        user_id,
        BuyerFinancialsUpsert(
            funding_source="all_cash",
            reported_cash_available=250000,
        ),
    )

    added = session.add.call_args.args[0]

    assert isinstance(added, BuyerFinancials)
    assert result is added
    assert added.buyer_id == buyer_id
    assert added.funding_source == "all_cash"
    assert added.reported_cash_available == Decimal("250000")
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(added)


def test_repository_updates_existing_financials() -> None:
    user_id = uuid4()
    buyer_id = uuid4()

    profile = BuyerProfile(
        id=buyer_id,
        user_id=user_id,
    )

    existing = BuyerFinancials(
        id=uuid4(),
        buyer_id=buyer_id,
        funding_source="sba_7a",
        reported_cash_available=Decimal("50000"),
    )

    session = MagicMock(spec=Session)
    session.scalar.side_effect = [
        profile,
        existing,
    ]

    repository = IntakeRepository(session)

    result = repository.upsert_buyer_financials(
        user_id,
        BuyerFinancialsUpsert(
            funding_source="all_cash",
            reported_cash_available=300000,
        ),
    )

    assert result is existing
    assert existing.funding_source == "all_cash"
    assert existing.reported_cash_available == Decimal("300000")
    session.add.assert_not_called()
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(existing)


def test_repository_requires_buyer_profile() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    repository = IntakeRepository(session)

    with pytest.raises(
        IntakeNotFoundError,
        match="Create the buyer profile",
    ):
        repository.upsert_buyer_financials(
            uuid4(),
            BuyerFinancialsUpsert(),
        )

    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_get_route_returns_authenticated_buyers_financials() -> None:
    user_id = uuid4()
    financials = build_financials_result()

    repository = MagicMock()
    repository.get_buyer_financials_by_user_id.return_value = (
        financials
    )

    response = get_buyer_financials(
        current_user_id=user_id,
        repository=repository,
    )

    assert response.id == financials.id
    assert response.buyer_id == financials.buyer_id
    assert response.verification_status == "verified"

    repository.get_buyer_financials_by_user_id.assert_called_once_with(
        user_id
    )


def test_get_route_returns_404_when_financials_are_absent() -> None:
    repository = MagicMock()
    repository.get_buyer_financials_by_user_id.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_buyer_financials(
            current_user_id=uuid4(),
            repository=repository,
        )

    assert exc_info.value.status_code == 404


def test_put_route_uses_authenticated_user() -> None:
    user_id = uuid4()
    financials = build_financials_result()

    repository = MagicMock()
    repository.upsert_buyer_financials.return_value = financials

    payload = BuyerFinancialsUpsert(
        funding_source="all_cash",
        reported_cash_available=250000,
    )

    response = upsert_buyer_financials(
        payload=payload,
        current_user_id=user_id,
        repository=repository,
    )

    assert response.id == financials.id

    repository.upsert_buyer_financials.assert_called_once_with(
        user_id,
        payload,
    )
