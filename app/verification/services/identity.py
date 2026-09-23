from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import VerificationStatus
from app.verification.exceptions import InvalidVerificationRequest, ProviderError
from app.verification.integrations.didit import DiditProvider
from app.verification.repositories import VerificationRepository
from app.verification.schemas import (
    DiditResult,
    IdentityWorkflow,
    ProviderSession,
    VerificationStatusResponse,
)


class IdentityService:
    def __init__(self, session: Session, provider: DiditProvider) -> None:
        self.session = session
        self.provider = provider
        self.repository = VerificationRepository(session)

    async def start_user_kyc(self, user_id: UUID) -> ProviderSession:
        user = self.repository.require_user(user_id)
        provider_session = await self.provider.create_session(
            IdentityWorkflow.INDIVIDUAL_KYC,
            f"user:{user_id}",
        )
        user.verification_status = VerificationStatus.PENDING
        user.verification_provider = "didit"
        user.provider_reference = provider_session.session_id
        user.verified_at = None
        self.session.commit()
        return provider_session

    def get_user_kyc_status(self, user_id: UUID) -> VerificationStatusResponse:
        user = self.repository.require_user(user_id)
        return VerificationStatusResponse(
            entity_id=user.id,
            status=user.verification_status,
            provider=user.verification_provider,
        )

    async def start_ein_check(
        self,
        business_id: UUID,
        user_id: UUID,
    ) -> ProviderSession:
        business = self.repository.require_owned_business(business_id, user_id)
        provider_session = await self.provider.create_session(
            IdentityWorkflow.EIN_CHECK,
            f"business:{business_id}",
        )
        business.verification_status = VerificationStatus.PENDING
        self.session.commit()
        return provider_session

    def get_ein_status(
        self,
        business_id: UUID,
        user_id: UUID,
    ) -> VerificationStatusResponse:
        business = self.repository.require_owned_business(business_id, user_id)
        return VerificationStatusResponse(
            entity_id=business.id,
            status=business.verification_status,
        )

    async def start_kyb(
        self,
        business_id: UUID,
        user_id: UUID,
    ) -> ProviderSession:
        self.repository.require_owned_business(business_id, user_id)
        financials = self.repository.get_business_financials_for_business(business_id)
        if financials is None:
            raise InvalidVerificationRequest(
                "Business financials are required before KYB"
            )
        provider_session = await self.provider.create_session(
            IdentityWorkflow.FULL_KYB,
            f"business:{business_id}",
        )
        financials.verification_status = VerificationStatus.PENDING
        financials.verification_provider = "didit"
        financials.provider_reference = provider_session.session_id
        financials.verified_at = None
        self.session.commit()
        return provider_session

    def get_kyb_status(
        self,
        business_id: UUID,
        user_id: UUID,
    ) -> VerificationStatusResponse:
        self.repository.require_owned_business(business_id, user_id)
        financials = self.repository.get_business_financials_for_business(business_id)
        if financials is None:
            raise InvalidVerificationRequest("Business financials do not exist")
        return VerificationStatusResponse(
            entity_id=business_id,
            status=financials.verification_status,
            provider=financials.verification_provider,
        )

    def apply_result(self, result: DiditResult) -> None:
        entity_kind, entity_id = _parse_vendor_data(result.vendor_data)
        verified_at = (
            datetime.now(timezone.utc)
            if result.status == VerificationStatus.VERIFIED
            else None
        )
        if result.workflow == IdentityWorkflow.INDIVIDUAL_KYC:
            if entity_kind != "user":
                raise ProviderError("Didit workflow/entity mismatch")
            user = self.repository.get_user_by_provider_reference(result.session_id)
            if user is None or user.id != entity_id:
                raise ProviderError("Didit session does not match a user")
            user.verification_status = result.status
            user.verification_provider = "didit"
            user.verified_at = verified_at
        elif result.workflow == IdentityWorkflow.EIN_CHECK:
            if entity_kind != "business":
                raise ProviderError("Didit workflow/entity mismatch")
            business = self.repository.get_business(entity_id)
            if business is None:
                raise ProviderError("Didit business was not found")
            business.verification_status = result.status
        elif result.workflow == IdentityWorkflow.FULL_KYB:
            if entity_kind != "business":
                raise ProviderError("Didit workflow/entity mismatch")
            financials = self.repository.get_business_financials_for_business(entity_id)
            if (
                financials is None
                or financials.provider_reference != result.session_id
            ):
                raise ProviderError("Didit session does not match business KYB")
            financials.verification_status = result.status
            financials.verification_provider = "didit"
            financials.verified_at = verified_at
            financials.provider_response = {
                "provider_status": result.provider_status,
                "workflow": result.workflow.value,
            }
        else:
            raise ProviderError("Unknown Didit workflow")
        self.session.commit()


def _parse_vendor_data(value: str) -> tuple[str, UUID]:
    try:
        kind, raw_id = value.split(":", 1)
        return kind, UUID(raw_id)
    except (ValueError, AttributeError) as exc:
        raise ProviderError("Didit vendor_data was invalid") from exc
