from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class BuyerType(str, Enum):
    FIRST_TIME_OWNER = "first_time_owner"
    EXISTING_BUSINESS_OWNER = "existing_business_owner"
    INVESTOR_GROUP = "investor_group"
    FAMILY_OFFICE = "family_office"
    PRIVATE_EQUITY = "private_equity"


class RealEstatePreference(str, Enum):
    INCLUDED = "included"
    LEASE = "lease"
    EITHER = "either"


class DealPreference(str, Enum):
    CASH = "cash"
    FINANCING = "financing"
    EITHER = "either"


class FundingSource(str, Enum):
    ALL_CASH = "all_cash"
    SBA_7A = "sba_7a"
    CONVENTIONAL = "conventional"
    INVESTOR_CAPITAL = "investor_capital"
    SELLER_FINANCING = "seller_financing"


class BusinessStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


class MatchStatus(str, Enum):
    MATCHED = "matched"
    INTERESTED = "interested"
    VERIFICATION = "verification"
    NDA = "nda"
    DUE_DILIGENCE = "due_diligence"
    OFFER = "offer"
    LOI = "loi"
    FINANCING = "financing"
    CLOSING = "closing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class DocumentType(str, Enum):
    BANK_STATEMENT = "bank_statement"
    TAX_RETURN = "tax_return"
    PROFIT_AND_LOSS = "profit_and_loss"
    BALANCE_SHEET = "balance_sheet"
    PROOF_OF_FUNDS = "proof_of_funds"
    LOAN_APPROVAL = "loan_approval"
    BUSINESS_LICENSE = "business_license"
    OTHER = "other"


class StorageProvider(str, Enum):
    CLOUDFLARE_R2 = "cloudflare_r2"


class LenderApprovedStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"