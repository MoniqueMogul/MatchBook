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


class NDAStatus(str, Enum):
    PENDING = "pending"
    BUYER_SIGNED = "buyer_signed"
    SELLER_SIGNED = "seller_signed"
    COMPLETED = "completed"


class NotificationType(str, Enum):
    NEW_MATCH = "new_match"
    MATCH_STATUS_CHANGED = "match_status_changed"
    NEW_MESSAGE = "new_message"
    NDA_SIGNED = "nda_signed"
    NDA_COMPLETED = "nda_completed"
    VERIFICATION_COMPLETED = "verification_completed"
    DOCUMENT_UPLOADED = "document_uploaded"
    DUE_DILIGENCE_UPDATE = "due_diligence_update"



class EventType(str, Enum):
    USER_CREATED = "user_created"
    BUYER_CREATED = "buyer_created"
    SELLER_CREATED = "seller_created"
    BUSINESS_CREATED = "business_created"
    BUYER_PREFERENCES_UPDATED = "buyer_preferences_updated"
    BUYER_FINANCIALS_UPDATED = "buyer_financials_updated"
    BUSINESS_UPDATED = "business_updated"
    MATCH_CREATED = "match_created"
    MATCH_STATUS_CHANGED = "match_status_changed"
    VERIFICATION_COMPLETED = "verification_completed"
    NDA_COMPLETED = "nda_completed"
    DOCUMENT_UPLOADED = "document_uploaded"
    MESSAGE_CREATED = "message_created"