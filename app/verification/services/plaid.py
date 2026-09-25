from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import VerificationStatus
from app.verification.integrations.plaid import (
    PlaidProvider,
    eligible_depository_balance,
)
from app.verification.repositories import VerificationRepository
from app.verification.schemas import (
    PlaidFundsResponse,
    PlaidLinkTokenResponse,
    VerificationStatusResponse,
)


class PlaidService:
    def __init__(self, session: Session, provider: PlaidProvider) -> None:
        self.session = session
        self.provider = provider
        self.repository = VerificationRepository(session)

    async def create_link_token(
        self,
        financials_id: UUID,
        user_id: UUID,
    ) -> PlaidLinkTokenResponse:
        self.repository.require_owned_buyer_financials(financials_id, user_id)
        data = await self.provider.create_link_token(str(financials_id))
        link_token = data.get("link_token")
        if not isinstance(link_token, str) or not link_token:
            from app.verification.exceptions import ProviderError

            raise ProviderError("Plaid link token response was invalid")
        return PlaidLinkTokenResponse(
            link_token=link_token,
            expiration=data.get("expiration"),
        )

    def get_status(
        self,
        financials_id: UUID,
        user_id: UUID,
    ) -> VerificationStatusResponse:
        financials = self.repository.require_owned_buyer_financials(
            financials_id,
            user_id,
        )
        return VerificationStatusResponse(
            entity_id=financials.id,
            status=financials.verification_status,
            provider=financials.verification_provider,
        )

    async def verify_funds(
        self,
        financials_id: UUID,
        user_id: UUID,
        public_token: str,
    ) -> PlaidFundsResponse:
        financials = self.repository.require_owned_buyer_financials(
            financials_id,
            user_id,
        )
        financials.verification_status = VerificationStatus.PENDING
        financials.verification_provider = "plaid"
        self.session.commit()
        try:
            exchanged = await self.provider.exchange_public_token(public_token)
            accounts = await self.provider.get_balances(exchanged["access_token"])
            eligible_balance, account_count = eligible_depository_balance(accounts)
            financials.verified_cash_amount = eligible_balance
            financials.verification_status = VerificationStatus.VERIFIED
            financials.verification_provider = "plaid"
            financials.provider_reference = exchanged["item_id"]
            financials.provider_response = {
                "eligible_account_count": account_count,
                "calculation": "positive_depository_available_or_current_balance",
            }
            financials.verified_at = datetime.now(timezone.utc)
            self.session.commit()
        except Exception:
            self.session.rollback()
            financials = self.repository.require_owned_buyer_financials(
                financials_id,
                user_id,
            )
            financials.verification_status = VerificationStatus.FAILED
            financials.verification_provider = "plaid"
            financials.provider_response = {"failure_code": "provider_failed"}
            financials.verified_at = None
            self.session.commit()
            raise

        return PlaidFundsResponse(
            buyer_financials_id=financials.id,
            eligible_balance=float(eligible_balance),
            eligible_account_count=account_count,
            verification_status=VerificationStatus.VERIFIED,
        )
