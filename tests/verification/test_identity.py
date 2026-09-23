import asyncio
import hashlib
import hmac
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.db_enum import VerificationStatus
from app.verification.config import VerificationSettings
from app.verification.exceptions import ProviderError, ResourceNotFoundError
from app.verification.integrations.didit import (
    DiditClient,
    canonical_json,
    map_didit_status,
)
from app.verification.schemas import DiditResult, IdentityWorkflow, ProviderSession
from app.verification.services.identity import IdentityService
from tests.verification.conftest import FakeSession


def provider_session(workflow):
    return ProviderSession(
        session_id=f"session-{workflow.value}",
        url="https://verify.invalid/session",
        workflow=workflow,
    )


def make_service():
    session = FakeSession()
    provider = MagicMock()
    provider.create_session = AsyncMock()
    service = IdentityService(session, provider)
    service.repository = MagicMock()
    return service, session, provider


def test_authenticated_user_starts_own_kyc():
    service, session, provider = make_service()
    user_id = uuid4()
    user = SimpleNamespace(
        id=user_id,
        verification_status=VerificationStatus.UNVERIFIED,
        verification_provider=None,
        provider_reference=None,
        verified_at=None,
    )
    service.repository.require_user.return_value = user
    provider.create_session.return_value = provider_session(
        IdentityWorkflow.INDIVIDUAL_KYC
    )

    result = asyncio.run(service.start_user_kyc(user_id))

    assert result.workflow == IdentityWorkflow.INDIVIDUAL_KYC
    provider.create_session.assert_awaited_once_with(
        IdentityWorkflow.INDIVIDUAL_KYC,
        f"user:{user_id}",
    )
    assert user.verification_status == VerificationStatus.PENDING
    assert user.provider_reference == result.session_id
    assert session.commits == 1


def test_kyc_status_is_current_user_only():
    service, _, _ = make_service()
    user_id = uuid4()
    service.repository.require_user.return_value = SimpleNamespace(
        id=user_id,
        verification_status=VerificationStatus.VERIFIED,
        verification_provider="didit",
    )
    result = service.get_user_kyc_status(user_id)
    assert result.entity_id == user_id
    service.repository.require_user.assert_called_once_with(user_id)


@pytest.mark.parametrize("workflow", ["ein", "kyb"])
def test_user_cannot_start_business_verification_for_another_owner(workflow):
    service, _, provider = make_service()
    service.repository.require_owned_business.side_effect = ResourceNotFoundError(
        "Business not found"
    )
    call = service.start_ein_check if workflow == "ein" else service.start_kyb

    with pytest.raises(ResourceNotFoundError):
        asyncio.run(call(uuid4(), uuid4()))

    provider.create_session.assert_not_awaited()


def test_owned_business_can_start_ein_check():
    service, _, provider = make_service()
    business_id = uuid4()
    business = SimpleNamespace(
        id=business_id,
        verification_status=VerificationStatus.UNVERIFIED,
    )
    service.repository.require_owned_business.return_value = business
    provider.create_session.return_value = provider_session(
        IdentityWorkflow.EIN_CHECK
    )

    asyncio.run(service.start_ein_check(business_id, uuid4()))

    assert business.verification_status == VerificationStatus.PENDING
    provider.create_session.assert_awaited_once()


def test_business_status_reads_enforce_owner():
    service, _, _ = make_service()
    service.repository.require_owned_business.side_effect = ResourceNotFoundError(
        "Business not found"
    )
    with pytest.raises(ResourceNotFoundError):
        service.get_ein_status(uuid4(), uuid4())
    with pytest.raises(ResourceNotFoundError):
        service.get_kyb_status(uuid4(), uuid4())


def test_owned_business_can_start_kyb_on_business_financials():
    service, _, provider = make_service()
    business_id = uuid4()
    financials = SimpleNamespace(
        verification_status=VerificationStatus.UNVERIFIED,
        verification_provider=None,
        provider_reference=None,
        verified_at=None,
    )
    service.repository.get_business_financials_for_business.return_value = financials
    provider.create_session.return_value = provider_session(IdentityWorkflow.FULL_KYB)

    result = asyncio.run(service.start_kyb(business_id, uuid4()))

    assert financials.verification_status == VerificationStatus.PENDING
    assert financials.provider_reference == result.session_id


def test_valid_didit_v2_signature_is_accepted_and_tampering_rejected():
    now = int(time.time())
    payload = {
        "timestamp": now,
        "session_id": "session-1",
        "workflow_id": "wf-kyc",
        "vendor_data": f"user:{uuid4()}",
        "status": "Approved",
    }
    settings = VerificationSettings(
        didit_webhook_secret="secret",
        didit_kyc_workflow_id="wf-kyc",
    )
    client = DiditClient(settings)
    signature = hmac.new(
        b"secret",
        canonical_json(payload).encode(),
        hashlib.sha256,
    ).hexdigest()

    assert client.verify_webhook(payload, signature, str(now), now=now)
    payload["status"] = "Declined"
    assert not client.verify_webhook(payload, signature, str(now), now=now)


def test_stale_or_invalid_didit_signature_is_rejected():
    client = DiditClient(VerificationSettings(didit_webhook_secret="secret"))
    payload = {"timestamp": 10}
    assert not client.verify_webhook(payload, "bad", "10", now=1000)


@pytest.mark.parametrize(
    ("provider_status", "internal_status"),
    [
        ("In Progress", VerificationStatus.PENDING),
        ("In Review", VerificationStatus.REQUIRES_REVIEW),
        ("Approved", VerificationStatus.VERIFIED),
        ("Declined", VerificationStatus.FAILED),
        ("Resubmission Requested", VerificationStatus.REQUIRES_REVIEW),
    ],
)
def test_provider_status_mapping(provider_status, internal_status):
    assert map_didit_status(provider_status) == internal_status


def test_unknown_provider_status_fails_safely():
    with pytest.raises(ProviderError, match="Unknown"):
        map_didit_status("Surprise Approval")


def test_unknown_or_unconfigured_workflow_fails_safely():
    client = DiditClient(
        VerificationSettings(didit_kyc_workflow_id="known-kyc")
    )
    with pytest.raises(ProviderError, match="invalid"):
        client.parse_webhook(
            {
                "session_id": "session",
                "workflow_id": "",
                "vendor_data": f"user:{uuid4()}",
                "status": "Approved",
            }
        )


def test_kyc_webhook_updates_only_session_bound_user():
    service, session, _ = make_service()
    user_id = uuid4()
    user = SimpleNamespace(
        id=user_id,
        verification_status=VerificationStatus.PENDING,
        verification_provider="didit",
        verified_at=None,
    )
    service.repository.get_user_by_provider_reference.return_value = user

    service.apply_result(
        DiditResult(
            session_id="session-1",
            workflow=IdentityWorkflow.INDIVIDUAL_KYC,
            status=VerificationStatus.VERIFIED,
            vendor_data=f"user:{user_id}",
            provider_status="Approved",
        )
    )

    assert user.verification_status == VerificationStatus.VERIFIED
    assert user.verified_at is not None
    assert session.commits == 1


def test_ein_webhook_updates_correct_business():
    service, _, _ = make_service()
    business_id = uuid4()
    business = SimpleNamespace(verification_status=VerificationStatus.PENDING)
    service.repository.get_business.return_value = business
    service.apply_result(
        DiditResult(
            session_id="ein-session",
            workflow=IdentityWorkflow.EIN_CHECK,
            status=VerificationStatus.VERIFIED,
            vendor_data=f"business:{business_id}",
            provider_status="Approved",
        )
    )
    assert business.verification_status == VerificationStatus.VERIFIED


def test_kyb_webhook_updates_bound_business_financials():
    service, _, _ = make_service()
    business_id = uuid4()
    financials = SimpleNamespace(
        provider_reference="kyb-session",
        verification_status=VerificationStatus.PENDING,
        verification_provider="didit",
        verified_at=None,
        provider_response=None,
    )
    service.repository.get_business_financials_for_business.return_value = financials
    service.apply_result(
        DiditResult(
            session_id="kyb-session",
            workflow=IdentityWorkflow.FULL_KYB,
            status=VerificationStatus.REQUIRES_REVIEW,
            vendor_data=f"business:{business_id}",
            provider_status="In Review",
        )
    )
    assert financials.verification_status == VerificationStatus.REQUIRES_REVIEW
    assert financials.provider_response["workflow"] == "full_kyb"


def test_malformed_provider_result_does_not_commit():
    service, session, _ = make_service()
    with pytest.raises(ProviderError):
        service.apply_result(
            DiditResult(
                session_id="session",
                workflow=IdentityWorkflow.EIN_CHECK,
                status=VerificationStatus.VERIFIED,
                vendor_data="not-an-entity",
                provider_status="Approved",
            )
        )
    assert session.commits == 0
