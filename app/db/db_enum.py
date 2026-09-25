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
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    REQUIRES_REVIEW = "requires_review"
    FAILED = "failed"


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


class NDASigningInitializationStatus(str, Enum):
    NOT_STARTED = "not_started"
    INITIALIZING = "initializing"
    READY = "ready"
    FAILED = "failed"


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


class DeclarationStatus(str, Enum):
    PENDING = "pending"
    SIGNED = "signed"


class OutboxStatus(str, Enum):
    PENDING = "pending"
    PUBLISHED = "published"

class EventConsumer(str, Enum):
    MATCHING = "matching"
    NOTIFICATION = "notification"
    CHAT = "chat"
    VERIFICATION = "verification"


class BusinessType(str, Enum):
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    PARTNERSHIP = "partnership"
    LLC = "llc"
    S_CORPORATION = "s_corporation"
    C_CORPORATION = "c_corporation"
    NONPROFIT = "nonprofit"
    OTHER = "other"




# ============================================================
# INDUSTRY
# What does the business do?
# ============================================================

class Industry(str, Enum):
    AUTOMOTIVE = "automotive"
    CONSTRUCTION_AND_TRADES = "construction_and_trades"
    MANUFACTURING = "manufacturing"
    FOOD_AND_BEVERAGE = "food_and_beverage"
    RETAIL = "retail"
    PROFESSIONAL_SERVICES = "professional_services"
    BUSINESS_SERVICES = "business_services"
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    BEAUTY_AND_PERSONAL_CARE = "beauty_and_personal_care"
    FITNESS_AND_WELLNESS = "fitness_and_wellness"
    EDUCATION_AND_CHILDCARE = "education_and_childcare"
    TRANSPORTATION_AND_LOGISTICS = "transportation_and_logistics"
    REAL_ESTATE_SERVICES = "real_estate_services"
    HOME_SERVICES = "home_services"
    HOSPITALITY_AND_TRAVEL = "hospitality_and_travel"
    ENTERTAINMENT_AND_RECREATION = "entertainment_and_recreation"
    PET_SERVICES = "pet_services"
    AGRICULTURE = "agriculture"
    WHOLESALE_AND_DISTRIBUTION = "wholesale_and_distribution"
    FINANCIAL_SERVICES = "financial_services"
    MEDIA_AND_CREATIVE = "media_and_creative"
    REPAIR_AND_MAINTENANCE = "repair_and_maintenance"
    OTHER = "other"


# ============================================================
# SUB-INDUSTRY
# What specifically does the business do?
# ============================================================

class SubIndustry(str, Enum):

    # --------------------------------------------------------
    # Automotive
    # --------------------------------------------------------

    AUTO_REPAIR_AND_MAINTENANCE = "auto_repair_and_maintenance"
    AUTO_BODY_AND_COLLISION_REPAIR = "auto_body_and_collision_repair"
    CAR_WASH_AND_DETAILING = "car_wash_and_detailing"
    TIRE_SHOP = "tire_shop"
    AUTO_PARTS_AND_ACCESSORIES = "auto_parts_and_accessories"
    TOWING_SERVICES = "towing_services"
    VEHICLE_DEALERSHIP = "vehicle_dealership"
    OTHER_AUTOMOTIVE = "other_automotive"

    # --------------------------------------------------------
    # Construction & Trades
    # --------------------------------------------------------

    GENERAL_CONTRACTING = "general_contracting"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    HVAC = "hvac"
    ROOFING = "roofing"
    PAINTING = "painting"
    FLOORING = "flooring"
    LANDSCAPING_AND_LAWN_CARE = "landscaping_and_lawn_care"
    CONCRETE_AND_MASONRY = "concrete_and_masonry"
    CARPENTRY = "carpentry"
    REMODELING_AND_RENOVATION = "remodeling_and_renovation"
    OTHER_CONSTRUCTION_AND_TRADES = "other_construction_and_trades"

    # --------------------------------------------------------
    # Manufacturing
    # --------------------------------------------------------

    FOOD_MANUFACTURING = "food_manufacturing"
    BEVERAGE_MANUFACTURING = "beverage_manufacturing"
    METAL_FABRICATION = "metal_fabrication"
    PLASTICS_AND_RUBBER_MANUFACTURING = "plastics_and_rubber_manufacturing"
    MACHINERY_AND_EQUIPMENT_MANUFACTURING = (
        "machinery_and_equipment_manufacturing"
    )
    FURNITURE_MANUFACTURING = "furniture_manufacturing"
    TEXTILE_AND_APPAREL_MANUFACTURING = (
        "textile_and_apparel_manufacturing"
    )
    CHEMICAL_MANUFACTURING = "chemical_manufacturing"
    ELECTRONICS_MANUFACTURING = "electronics_manufacturing"
    OTHER_MANUFACTURING = "other_manufacturing"

    # --------------------------------------------------------
    # Food & Beverage
    # --------------------------------------------------------

    FULL_SERVICE_RESTAURANT = "full_service_restaurant"
    FAST_CASUAL_RESTAURANT = "fast_casual_restaurant"
    QUICK_SERVICE_RESTAURANT = "quick_service_restaurant"
    CAFE_AND_COFFEE_SHOP = "cafe_and_coffee_shop"
    BAKERY = "bakery"
    BAR_AND_PUB = "bar_and_pub"
    CATERING = "catering"
    FOOD_TRUCK = "food_truck"
    OTHER_FOOD_AND_BEVERAGE = "other_food_and_beverage"

    # --------------------------------------------------------
    # Retail
    # --------------------------------------------------------

    GROCERY_AND_CONVENIENCE = "grocery_and_convenience"
    CLOTHING_AND_APPAREL = "clothing_and_apparel"
    ELECTRONICS_RETAIL = "electronics_retail"
    FURNITURE_AND_HOME_GOODS = "furniture_and_home_goods"
    HARDWARE_AND_HOME_IMPROVEMENT = "hardware_and_home_improvement"
    HEALTH_AND_BEAUTY_RETAIL = "health_and_beauty_retail"
    JEWELRY = "jewelry"
    PET_RETAIL = "pet_retail"
    SPECIALTY_RETAIL = "specialty_retail"
    OTHER_RETAIL = "other_retail"

    # --------------------------------------------------------
    # Professional Services
    # --------------------------------------------------------

    ACCOUNTING_AND_BOOKKEEPING = "accounting_and_bookkeeping"
    LEGAL_SERVICES = "legal_services"
    CONSULTING = "consulting"
    MARKETING_AND_ADVERTISING = "marketing_and_advertising"
    ARCHITECTURE = "architecture"
    ENGINEERING_SERVICES = "engineering_services"
    RECRUITING_AND_STAFFING = "recruiting_and_staffing"
    TRANSLATION_SERVICES = "translation_services"
    OTHER_PROFESSIONAL_SERVICES = "other_professional_services"

    # --------------------------------------------------------
    # Business Services
    # --------------------------------------------------------

    COMMERCIAL_CLEANING = "commercial_cleaning"
    SECURITY_SERVICES = "security_services"
    PEST_CONTROL = "pest_control"
    PRINTING_AND_SIGNAGE = "printing_and_signage"
    EQUIPMENT_RENTAL = "equipment_rental"
    WASTE_MANAGEMENT = "waste_management"
    FACILITY_MANAGEMENT = "facility_management"
    LAUNDRY_AND_LINEN_SERVICES = "laundry_and_linen_services"
    OTHER_BUSINESS_SERVICES = "other_business_services"

    # --------------------------------------------------------
    # Technology
    # --------------------------------------------------------

    SAAS = "saas"
    SOFTWARE_DEVELOPMENT = "software_development"
    IT_SERVICES = "it_services"
    MANAGED_IT_SERVICES = "managed_it_services"
    CYBERSECURITY = "cybersecurity"
    WEB_DEVELOPMENT = "web_development"
    DATA_AND_ANALYTICS = "data_and_analytics"
    HOSTING_AND_CLOUD_SERVICES = "hosting_and_cloud_services"
    OTHER_TECHNOLOGY = "other_technology"

    # --------------------------------------------------------
    # Healthcare
    # --------------------------------------------------------

    MEDICAL_PRACTICE = "medical_practice"
    DENTAL_PRACTICE = "dental_practice"
    PHYSICAL_THERAPY = "physical_therapy"
    CHIROPRACTIC = "chiropractic"
    HOME_HEALTHCARE = "home_healthcare"
    MENTAL_AND_BEHAVIORAL_HEALTH = "mental_and_behavioral_health"
    MEDICAL_EQUIPMENT_AND_SUPPLIES = "medical_equipment_and_supplies"
    OTHER_HEALTHCARE = "other_healthcare"

    # --------------------------------------------------------
    # Beauty & Personal Care
    # --------------------------------------------------------

    HAIR_SALON = "hair_salon"
    BARBERSHOP = "barbershop"
    NAIL_SALON = "nail_salon"
    SPA = "spa"
    MED_SPA = "med_spa"
    BEAUTY_SERVICES = "beauty_services"
    OTHER_BEAUTY_AND_PERSONAL_CARE = "other_beauty_and_personal_care"

    # --------------------------------------------------------
    # Fitness & Wellness
    # --------------------------------------------------------

    GYM_AND_FITNESS_CENTER = "gym_and_fitness_center"
    PERSONAL_TRAINING = "personal_training"
    YOGA_AND_PILATES_STUDIO = "yoga_and_pilates_studio"
    WELLNESS_CENTER = "wellness_center"
    OTHER_FITNESS_AND_WELLNESS = "other_fitness_and_wellness"

    # --------------------------------------------------------
    # Education & Childcare
    # --------------------------------------------------------

    DAYCARE_AND_CHILDCARE = "daycare_and_childcare"
    TUTORING = "tutoring"
    TRAINING_CENTER = "training_center"
    TRADE_AND_VOCATIONAL_SCHOOL = "trade_and_vocational_school"
    ONLINE_EDUCATION = "online_education"
    OTHER_EDUCATION_AND_CHILDCARE = "other_education_and_childcare"

    # --------------------------------------------------------
    # Transportation & Logistics
    # --------------------------------------------------------

    TRUCKING = "trucking"
    FREIGHT_AND_LOGISTICS = "freight_and_logistics"
    COURIER_AND_DELIVERY = "courier_and_delivery"
    MOVING_COMPANY = "moving_company"
    WAREHOUSING = "warehousing"
    PASSENGER_TRANSPORTATION = "passenger_transportation"
    OTHER_TRANSPORTATION_AND_LOGISTICS = (
        "other_transportation_and_logistics"
    )

    # --------------------------------------------------------
    # Real Estate Services
    # --------------------------------------------------------

    PROPERTY_MANAGEMENT = "property_management"
    REAL_ESTATE_BROKERAGE = "real_estate_brokerage"
    HOME_INSPECTION = "home_inspection"
    APPRAISAL_SERVICES = "appraisal_services"
    TITLE_AND_ESCROW_SERVICES = "title_and_escrow_services"
    OTHER_REAL_ESTATE_SERVICES = "other_real_estate_services"

    # --------------------------------------------------------
    # Home Services
    # --------------------------------------------------------

    RESIDENTIAL_CLEANING = "residential_cleaning"
    POOL_SERVICES = "pool_services"
    APPLIANCE_REPAIR = "appliance_repair"
    HANDYMAN_SERVICES = "handyman_services"
    GARAGE_DOOR_SERVICES = "garage_door_services"
    LOCKSMITH_SERVICES = "locksmith_services"
    OTHER_HOME_SERVICES = "other_home_services"

    # --------------------------------------------------------
    # Hospitality & Travel
    # --------------------------------------------------------

    HOTEL = "hotel"
    MOTEL = "motel"
    BED_AND_BREAKFAST = "bed_and_breakfast"
    VACATION_RENTAL_MANAGEMENT = "vacation_rental_management"
    TRAVEL_AGENCY = "travel_agency"
    TOUR_OPERATOR = "tour_operator"
    OTHER_HOSPITALITY_AND_TRAVEL = "other_hospitality_and_travel"

    # --------------------------------------------------------
    # Entertainment & Recreation
    # --------------------------------------------------------

    EVENT_PLANNING = "event_planning"
    EVENT_VENUE = "event_venue"
    PHOTOGRAPHY_AND_VIDEOGRAPHY = "photography_and_videography"
    ENTERTAINMENT_VENUE = "entertainment_venue"
    RECREATION_BUSINESS = "recreation_business"
    GAMING_AND_ENTERTAINMENT = "gaming_and_entertainment"
    OTHER_ENTERTAINMENT_AND_RECREATION = (
        "other_entertainment_and_recreation"
    )

    # --------------------------------------------------------
    # Pet Services
    # --------------------------------------------------------

    VETERINARY_CLINIC = "veterinary_clinic"
    PET_GROOMING = "pet_grooming"
    PET_BOARDING = "pet_boarding"
    DOG_TRAINING = "dog_training"
    PET_DAYCARE = "pet_daycare"
    OTHER_PET_SERVICES = "other_pet_services"

    # --------------------------------------------------------
    # Agriculture
    # --------------------------------------------------------

    FARMING = "farming"
    LIVESTOCK = "livestock"
    AGRICULTURAL_SERVICES = "agricultural_services"
    NURSERY_AND_GREENHOUSE = "nursery_and_greenhouse"
    OTHER_AGRICULTURE = "other_agriculture"

    # --------------------------------------------------------
    # Wholesale & Distribution
    # --------------------------------------------------------

    FOOD_AND_BEVERAGE_DISTRIBUTION = "food_and_beverage_distribution"
    INDUSTRIAL_DISTRIBUTION = "industrial_distribution"
    CONSUMER_GOODS_DISTRIBUTION = "consumer_goods_distribution"
    BUILDING_MATERIALS_DISTRIBUTION = "building_materials_distribution"
    MEDICAL_DISTRIBUTION = "medical_distribution"
    OTHER_WHOLESALE_AND_DISTRIBUTION = "other_wholesale_and_distribution"

    # --------------------------------------------------------
    # Financial Services
    # --------------------------------------------------------

    INSURANCE_AGENCY = "insurance_agency"
    TAX_PREPARATION = "tax_preparation"
    FINANCIAL_PLANNING = "financial_planning"
    MORTGAGE_SERVICES = "mortgage_services"
    OTHER_FINANCIAL_SERVICES = "other_financial_services"

    # --------------------------------------------------------
    # Media & Creative
    # --------------------------------------------------------

    GRAPHIC_DESIGN = "graphic_design"
    PHOTOGRAPHY = "photography"
    VIDEO_PRODUCTION = "video_production"
    PUBLISHING = "publishing"
    DIGITAL_MEDIA = "digital_media"
    CREATIVE_AGENCY = "creative_agency"
    OTHER_MEDIA_AND_CREATIVE = "other_media_and_creative"

    # --------------------------------------------------------
    # Repair & Maintenance
    # --------------------------------------------------------

    ELECTRONICS_REPAIR = "electronics_repair"
    EQUIPMENT_REPAIR = "equipment_repair"
    MACHINERY_REPAIR = "machinery_repair"
    FURNITURE_REPAIR = "furniture_repair"
    GENERAL_REPAIR_SERVICES = "general_repair_services"
    OTHER_REPAIR_AND_MAINTENANCE = "other_repair_and_maintenance"

    # --------------------------------------------------------
    # Other
    # --------------------------------------------------------

    OTHER = "other"


# ============================================================
# BUSINESS MODEL
# How does the business make money?
# ============================================================

class BusinessModel(str, Enum):
    PRODUCT_SALES = "product_sales"
    TRANSACTIONAL = "transactional"
    PROJECT_BASED = "project_based"
    RECURRING_SERVICE = "recurring_service"
    SUBSCRIPTION = "subscription"
    MEMBERSHIP = "membership"
    CONTRACT_BASED = "contract_based"
    RENTAL_AND_LEASING = "rental_and_leasing"
    COMMISSION_AND_BROKERAGE = "commission_and_brokerage"
    LICENSING = "licensing"
    MARKETPLACE_AND_PLATFORM = "marketplace_and_platform"
    ADVERTISING = "advertising"
    FRANCHISE = "franchise"
    USAGE_BASED = "usage_based"
    OTHER = "other"
