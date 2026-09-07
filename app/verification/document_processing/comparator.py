from app.verification.services.financial_verification_service import DEFAULT_TOLERANCE, FieldComparison, _compare_field


def compare_document_to_claim(extracted_value, claimed_value, field_name: str) -> FieldComparison:
    return _compare_field(field_name, claimed_value, extracted_value, DEFAULT_TOLERANCE)


def compare_multi_source(field_name: str, claimed, sources: dict) -> list:
    return [_compare_field(f"{field_name}_vs_{source_name}", claimed, value) for source_name, value in sources.items()]