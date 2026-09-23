from app.db.db_enum import Industry, BusinessModel
from app.db.industry_mapping import INDUSTRY_SUB_INDUSTRIES
from app.intake.schemas.common import IndustryOption, SubIndustryOption, BusinessModelOption


def enum_label(value: str) -> str:
    """
    Converts:
        construction_and_trades

    into:
        Construction And Trades
    """
    return value.replace("_", " ").title()


def get_industry_options() -> list[IndustryOption]:
    return [
        IndustryOption(
            value=industry,
            label=enum_label(industry.value),
            sub_industries=[
                SubIndustryOption(
                    value=sub_industry,
                    label=enum_label(sub_industry.value),
                )
                for sub_industry in sorted(
                    INDUSTRY_SUB_INDUSTRIES[industry],
                    key=lambda item: item.value,
                )
            ],
        )
        for industry in Industry
    ]


def get_business_model_options() -> list[BusinessModelOption]:
    return [
        BusinessModelOption(
            value=business_model,
            label=enum_label(business_model.value),
        )
        for business_model in BusinessModel
    ]