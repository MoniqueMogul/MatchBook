from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.db.db_enum import VerificationStatus
from app.verification.exceptions import NDAEligibilityError, ResourceNotFoundError
from app.verification.repositories import VerificationRepository
from app.verification.schemas import NDAIneligibilityReason
from app.verification.services.nda_eligibility import NDAEligibilityService
from tests.verification.conftest import FakeSession


def verified_match(*, document_statuses=None):
    """Build the exact Match -> profile/entity/financial/document graph checked."""
    if document_statuses is None:
        document_statuses = [VerificationStatus.VERIFIED]
    business_financials = SimpleNamespace(
        verification_status=VerificationStatus.VERIFIED,
        documents=[
            SimpleNamespace(verification_status=status)
            for status in document_statuses
        ],
    )
    return SimpleNamespace(
        buyer=SimpleNamespace(
            user=SimpleNamespace(
                verification_status=VerificationStatus.VERIFIED
            ),
            financials=SimpleNamespace(
                verification_status=VerificationStatus.VERIFIED
            ),
        ),
        business=SimpleNamespace(
            verification_status=VerificationStatus.VERIFIED,
            seller=SimpleNamespace(
                user=SimpleNamespace(
                    verification_status=VerificationStatus.VERIFIED
                )
            ),
            financials=business_financials,
        ),
    )


def make_service(match):
    service = NDAEligibilityService(FakeSession())
    service.repository = MagicMock()
    service.repository.require_match_verification_context.return_value = match
    return service


def missing_values(result):
    return [reason.value for reason in result.missing]


def test_everything_verified_is_eligible_and_require_returns_normally():
    service = make_service(verified_match())
    match_id = uuid4()

    result = service.get_nda_eligibility(match_id)

    assert result.eligible is True
    assert result.missing == []
    assert service.require_nda_eligibility(match_id) is None
    service.repository.require_match_verification_context.assert_called_with(match_id)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda match: setattr(
                match.buyer.user,
                "verification_status",
                VerificationStatus.PENDING,
            ),
            "buyer_kyc",
        ),
        (
            lambda match: setattr(match.buyer, "financials", None),
            "buyer_financial_verification",
        ),
        (
            lambda match: setattr(
                match.business.seller.user,
                "verification_status",
                VerificationStatus.FAILED,
            ),
            "seller_kyc",
        ),
        (
            lambda match: setattr(
                match.business,
                "verification_status",
                VerificationStatus.REQUIRES_REVIEW,
            ),
            "business_kyb",
        ),
        (
            lambda match: setattr(
                match.business.financials,
                "verification_status",
                VerificationStatus.PENDING,
            ),
            "business_kyb",
        ),
        (
            lambda match: setattr(
                match.business.financials.documents[0],
                "verification_status",
                VerificationStatus.PENDING,
            ),
            "business_financial_verification",
        ),
    ],
)
def test_each_authoritative_requirement_can_block_nda(mutate, reason):
    match = verified_match()
    mutate(match)

    result = make_service(match).get_nda_eligibility(uuid4())

    assert result.eligible is False
    assert missing_values(result) == [reason]


@pytest.mark.parametrize(
    "status",
    [
        VerificationStatus.FAILED,
        VerificationStatus.REQUIRES_REVIEW,
        VerificationStatus.PENDING,
    ],
)
def test_incomplete_business_document_statuses_do_not_pass(status):
    result = make_service(
        verified_match(document_statuses=[status])
    ).get_nda_eligibility(uuid4())

    assert missing_values(result) == ["business_financial_verification"]


def test_no_business_documents_does_not_pass_vacuously():
    result = make_service(
        verified_match(document_statuses=[])
    ).get_nda_eligibility(uuid4())

    assert missing_values(result) == ["business_financial_verification"]


def test_missing_business_financials_fails_kyb_and_documents():
    match = verified_match()
    match.business.financials = None

    result = make_service(match).get_nda_eligibility(uuid4())

    assert missing_values(result) == [
        "business_kyb",
        "business_financial_verification",
    ]


def test_multiple_missing_reasons_are_returned_together():
    match = verified_match()
    match.buyer.user.verification_status = VerificationStatus.FAILED
    match.buyer.financials.verification_status = VerificationStatus.PENDING
    match.business.seller.user.verification_status = (
        VerificationStatus.REQUIRES_REVIEW
    )

    result = make_service(match).get_nda_eligibility(uuid4())

    assert missing_values(result) == [
        "buyer_kyc",
        "buyer_financial_verification",
        "seller_kyc",
    ]


def test_nonexistent_match_raises_controlled_not_found_error():
    service = make_service(verified_match())
    service.repository.require_match_verification_context.side_effect = (
        ResourceNotFoundError("Match not found")
    )

    with pytest.raises(ResourceNotFoundError, match="Match not found"):
        service.get_nda_eligibility(uuid4())


def test_repository_loader_raises_not_found_for_nonexistent_match():
    session = MagicMock()
    result = session.execute.return_value.unique.return_value
    result.scalar_one_or_none.return_value = None

    with pytest.raises(ResourceNotFoundError, match="Match not found"):
        VerificationRepository(session).require_match_verification_context(
            uuid4()
        )


def test_require_uses_same_decision_and_exposes_machine_readable_reasons():
    match = verified_match()
    match.buyer.financials.verification_status = VerificationStatus.FAILED
    service = make_service(match)
    match_id = uuid4()

    expected = service.get_nda_eligibility(match_id)
    with pytest.raises(NDAEligibilityError) as raised:
        service.require_nda_eligibility(match_id)

    assert raised.value.missing == expected.missing
    assert raised.value.missing == [
        NDAIneligibilityReason.BUYER_FINANCIAL_VERIFICATION
    ]


def test_eligibility_accepts_only_match_id_not_frontend_verification_state():
    parameters = inspect.signature(
        NDAEligibilityService.get_nda_eligibility
    ).parameters

    assert list(parameters) == ["self", "match_id"]
