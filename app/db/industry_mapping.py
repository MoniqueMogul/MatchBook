from app.db.db_enum import Industry, SubIndustry

INDUSTRY_SUB_INDUSTRIES: dict[Industry, frozenset[SubIndustry]] = {

    Industry.AUTOMOTIVE: frozenset({
        SubIndustry.AUTO_REPAIR_AND_MAINTENANCE,
        SubIndustry.AUTO_BODY_AND_COLLISION_REPAIR,
        SubIndustry.CAR_WASH_AND_DETAILING,
        SubIndustry.TIRE_SHOP,
        SubIndustry.AUTO_PARTS_AND_ACCESSORIES,
        SubIndustry.TOWING_SERVICES,
        SubIndustry.VEHICLE_DEALERSHIP,
        SubIndustry.OTHER_AUTOMOTIVE,
    }),

    Industry.CONSTRUCTION_AND_TRADES: frozenset({
        SubIndustry.GENERAL_CONTRACTING,
        SubIndustry.ELECTRICAL,
        SubIndustry.PLUMBING,
        SubIndustry.HVAC,
        SubIndustry.ROOFING,
        SubIndustry.PAINTING,
        SubIndustry.FLOORING,
        SubIndustry.LANDSCAPING_AND_LAWN_CARE,
        SubIndustry.CONCRETE_AND_MASONRY,
        SubIndustry.CARPENTRY,
        SubIndustry.REMODELING_AND_RENOVATION,
        SubIndustry.OTHER_CONSTRUCTION_AND_TRADES,
    }),

    Industry.MANUFACTURING: frozenset({
        SubIndustry.FOOD_MANUFACTURING,
        SubIndustry.BEVERAGE_MANUFACTURING,
        SubIndustry.METAL_FABRICATION,
        SubIndustry.PLASTICS_AND_RUBBER_MANUFACTURING,
        SubIndustry.MACHINERY_AND_EQUIPMENT_MANUFACTURING,
        SubIndustry.FURNITURE_MANUFACTURING,
        SubIndustry.TEXTILE_AND_APPAREL_MANUFACTURING,
        SubIndustry.CHEMICAL_MANUFACTURING,
        SubIndustry.ELECTRONICS_MANUFACTURING,
        SubIndustry.OTHER_MANUFACTURING,
    }),

    Industry.FOOD_AND_BEVERAGE: frozenset({
        SubIndustry.FULL_SERVICE_RESTAURANT,
        SubIndustry.FAST_CASUAL_RESTAURANT,
        SubIndustry.QUICK_SERVICE_RESTAURANT,
        SubIndustry.CAFE_AND_COFFEE_SHOP,
        SubIndustry.BAKERY,
        SubIndustry.BAR_AND_PUB,
        SubIndustry.CATERING,
        SubIndustry.FOOD_TRUCK,
        SubIndustry.OTHER_FOOD_AND_BEVERAGE,
    }),

    Industry.RETAIL: frozenset({
        SubIndustry.GROCERY_AND_CONVENIENCE,
        SubIndustry.CLOTHING_AND_APPAREL,
        SubIndustry.ELECTRONICS_RETAIL,
        SubIndustry.FURNITURE_AND_HOME_GOODS,
        SubIndustry.HARDWARE_AND_HOME_IMPROVEMENT,
        SubIndustry.HEALTH_AND_BEAUTY_RETAIL,
        SubIndustry.JEWELRY,
        SubIndustry.PET_RETAIL,
        SubIndustry.SPECIALTY_RETAIL,
        SubIndustry.OTHER_RETAIL,
    }),

    Industry.PROFESSIONAL_SERVICES: frozenset({
        SubIndustry.ACCOUNTING_AND_BOOKKEEPING,
        SubIndustry.LEGAL_SERVICES,
        SubIndustry.CONSULTING,
        SubIndustry.MARKETING_AND_ADVERTISING,
        SubIndustry.ARCHITECTURE,
        SubIndustry.ENGINEERING_SERVICES,
        SubIndustry.RECRUITING_AND_STAFFING,
        SubIndustry.TRANSLATION_SERVICES,
        SubIndustry.OTHER_PROFESSIONAL_SERVICES,
    }),

    Industry.BUSINESS_SERVICES: frozenset({
        SubIndustry.COMMERCIAL_CLEANING,
        SubIndustry.SECURITY_SERVICES,
        SubIndustry.PEST_CONTROL,
        SubIndustry.PRINTING_AND_SIGNAGE,
        SubIndustry.EQUIPMENT_RENTAL,
        SubIndustry.WASTE_MANAGEMENT,
        SubIndustry.FACILITY_MANAGEMENT,
        SubIndustry.LAUNDRY_AND_LINEN_SERVICES,
        SubIndustry.OTHER_BUSINESS_SERVICES,
    }),

    Industry.TECHNOLOGY: frozenset({
        SubIndustry.SAAS,
        SubIndustry.SOFTWARE_DEVELOPMENT,
        SubIndustry.IT_SERVICES,
        SubIndustry.MANAGED_IT_SERVICES,
        SubIndustry.CYBERSECURITY,
        SubIndustry.WEB_DEVELOPMENT,
        SubIndustry.DATA_AND_ANALYTICS,
        SubIndustry.HOSTING_AND_CLOUD_SERVICES,
        SubIndustry.OTHER_TECHNOLOGY,
    }),

    Industry.HEALTHCARE: frozenset({
        SubIndustry.MEDICAL_PRACTICE,
        SubIndustry.DENTAL_PRACTICE,
        SubIndustry.PHYSICAL_THERAPY,
        SubIndustry.CHIROPRACTIC,
        SubIndustry.HOME_HEALTHCARE,
        SubIndustry.MENTAL_AND_BEHAVIORAL_HEALTH,
        SubIndustry.MEDICAL_EQUIPMENT_AND_SUPPLIES,
        SubIndustry.OTHER_HEALTHCARE,
    }),

    Industry.BEAUTY_AND_PERSONAL_CARE: frozenset({
        SubIndustry.HAIR_SALON,
        SubIndustry.BARBERSHOP,
        SubIndustry.NAIL_SALON,
        SubIndustry.SPA,
        SubIndustry.MED_SPA,
        SubIndustry.BEAUTY_SERVICES,
        SubIndustry.OTHER_BEAUTY_AND_PERSONAL_CARE,
    }),

    Industry.FITNESS_AND_WELLNESS: frozenset({
        SubIndustry.GYM_AND_FITNESS_CENTER,
        SubIndustry.PERSONAL_TRAINING,
        SubIndustry.YOGA_AND_PILATES_STUDIO,
        SubIndustry.WELLNESS_CENTER,
        SubIndustry.OTHER_FITNESS_AND_WELLNESS,
    }),

    Industry.EDUCATION_AND_CHILDCARE: frozenset({
        SubIndustry.DAYCARE_AND_CHILDCARE,
        SubIndustry.TUTORING,
        SubIndustry.TRAINING_CENTER,
        SubIndustry.TRADE_AND_VOCATIONAL_SCHOOL,
        SubIndustry.ONLINE_EDUCATION,
        SubIndustry.OTHER_EDUCATION_AND_CHILDCARE,
    }),

    Industry.TRANSPORTATION_AND_LOGISTICS: frozenset({
        SubIndustry.TRUCKING,
        SubIndustry.FREIGHT_AND_LOGISTICS,
        SubIndustry.COURIER_AND_DELIVERY,
        SubIndustry.MOVING_COMPANY,
        SubIndustry.WAREHOUSING,
        SubIndustry.PASSENGER_TRANSPORTATION,
        SubIndustry.OTHER_TRANSPORTATION_AND_LOGISTICS,
    }),

    Industry.REAL_ESTATE_SERVICES: frozenset({
        SubIndustry.PROPERTY_MANAGEMENT,
        SubIndustry.REAL_ESTATE_BROKERAGE,
        SubIndustry.HOME_INSPECTION,
        SubIndustry.APPRAISAL_SERVICES,
        SubIndustry.TITLE_AND_ESCROW_SERVICES,
        SubIndustry.OTHER_REAL_ESTATE_SERVICES,
    }),

    Industry.HOME_SERVICES: frozenset({
        SubIndustry.RESIDENTIAL_CLEANING,
        SubIndustry.POOL_SERVICES,
        SubIndustry.APPLIANCE_REPAIR,
        SubIndustry.HANDYMAN_SERVICES,
        SubIndustry.GARAGE_DOOR_SERVICES,
        SubIndustry.LOCKSMITH_SERVICES,
        SubIndustry.OTHER_HOME_SERVICES,
    }),

    Industry.HOSPITALITY_AND_TRAVEL: frozenset({
        SubIndustry.HOTEL,
        SubIndustry.MOTEL,
        SubIndustry.BED_AND_BREAKFAST,
        SubIndustry.VACATION_RENTAL_MANAGEMENT,
        SubIndustry.TRAVEL_AGENCY,
        SubIndustry.TOUR_OPERATOR,
        SubIndustry.OTHER_HOSPITALITY_AND_TRAVEL,
    }),

    Industry.ENTERTAINMENT_AND_RECREATION: frozenset({
        SubIndustry.EVENT_PLANNING,
        SubIndustry.EVENT_VENUE,
        SubIndustry.PHOTOGRAPHY_AND_VIDEOGRAPHY,
        SubIndustry.ENTERTAINMENT_VENUE,
        SubIndustry.RECREATION_BUSINESS,
        SubIndustry.GAMING_AND_ENTERTAINMENT,
        SubIndustry.OTHER_ENTERTAINMENT_AND_RECREATION,
    }),

    Industry.PET_SERVICES: frozenset({
        SubIndustry.VETERINARY_CLINIC,
        SubIndustry.PET_GROOMING,
        SubIndustry.PET_BOARDING,
        SubIndustry.DOG_TRAINING,
        SubIndustry.PET_DAYCARE,
        SubIndustry.OTHER_PET_SERVICES,
    }),

    Industry.AGRICULTURE: frozenset({
        SubIndustry.FARMING,
        SubIndustry.LIVESTOCK,
        SubIndustry.AGRICULTURAL_SERVICES,
        SubIndustry.NURSERY_AND_GREENHOUSE,
        SubIndustry.OTHER_AGRICULTURE,
    }),

    Industry.WHOLESALE_AND_DISTRIBUTION: frozenset({
        SubIndustry.FOOD_AND_BEVERAGE_DISTRIBUTION,
        SubIndustry.INDUSTRIAL_DISTRIBUTION,
        SubIndustry.CONSUMER_GOODS_DISTRIBUTION,
        SubIndustry.BUILDING_MATERIALS_DISTRIBUTION,
        SubIndustry.MEDICAL_DISTRIBUTION,
        SubIndustry.OTHER_WHOLESALE_AND_DISTRIBUTION,
    }),

    Industry.FINANCIAL_SERVICES: frozenset({
        SubIndustry.INSURANCE_AGENCY,
        SubIndustry.TAX_PREPARATION,
        SubIndustry.FINANCIAL_PLANNING,
        SubIndustry.MORTGAGE_SERVICES,
        SubIndustry.OTHER_FINANCIAL_SERVICES,
    }),

    Industry.MEDIA_AND_CREATIVE: frozenset({
        SubIndustry.GRAPHIC_DESIGN,
        SubIndustry.PHOTOGRAPHY,
        SubIndustry.VIDEO_PRODUCTION,
        SubIndustry.PUBLISHING,
        SubIndustry.DIGITAL_MEDIA,
        SubIndustry.CREATIVE_AGENCY,
        SubIndustry.OTHER_MEDIA_AND_CREATIVE,
    }),

    Industry.REPAIR_AND_MAINTENANCE: frozenset({
        SubIndustry.ELECTRONICS_REPAIR,
        SubIndustry.EQUIPMENT_REPAIR,
        SubIndustry.MACHINERY_REPAIR,
        SubIndustry.FURNITURE_REPAIR,
        SubIndustry.GENERAL_REPAIR_SERVICES,
        SubIndustry.OTHER_REPAIR_AND_MAINTENANCE,
    }),

    Industry.OTHER: frozenset({
        SubIndustry.OTHER,
    }),
}