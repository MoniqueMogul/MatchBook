from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import VerificationStatus
from app.verification.exceptions import NDAEligibilityError
from app.verification.repositories import VerificationRepository
from app.verification.schemas import NDAEligibilityResult, NDAIneligibilityReason


class NDAEligibilityService:
    """Derive whether a match's authoritative verification state permits NDA."""

    def __init__(self, session: Session) -> None:
        self.repository = VerificationRepository(session)

    def get_nda_eligibility(self, match_id: UUID) -> NDAEligibilityResult:
        match = self.repository.require_match_verification_context(match_id)
        missing: list[NDAIneligibilityReason] = []

        buyer = match.buyer
        if buyer.user.verification_status != VerificationStatus.VERIFIED:
            missing.append(NDAIneligibilityReason.BUYER_KYC)
        if (
            buyer.financials is None
            or buyer.financials.verification_status != VerificationStatus.VERIFIED
        ):
            missing.append(NDAIneligibilityReason.BUYER_FINANCIAL_VERIFICATION)

        business = match.business
        if business.seller.user.verification_status != VerificationStatus.VERIFIED:
            missing.append(NDAIneligibilityReason.SELLER_KYC)

        # The rebuilt identity flow stores the EIN/business decision on Business
        # and the full-KYB decision on BusinessFinancials. Both must be complete.
        business_financials = business.financials
        if (
            business.verification_status != VerificationStatus.VERIFIED
            or business_financials is None
            or business_financials.verification_status
            != VerificationStatus.VERIFIED
        ):
            missing.append(NDAIneligibilityReason.BUSINESS_KYB)

        # The current product model defines no required document taxonomy. The
        # applicable set is every document attached to this BusinessFinancials
        # record; it must be non-empty and every document must be VERIFIED.
        documents = business_financials.documents if business_financials else []
        if not documents or any(
            document.verification_status != VerificationStatus.VERIFIED
            for document in documents
        ):
            missing.append(
                NDAIneligibilityReason.BUSINESS_FINANCIAL_VERIFICATION
            )

        return NDAEligibilityResult(eligible=not missing, missing=missing)

    def require_nda_eligibility(self, match_id: UUID) -> None:
        result = self.get_nda_eligibility(match_id)
        if not result.eligible:
            raise NDAEligibilityError(result.missing)
