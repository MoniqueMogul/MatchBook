LOW_CONFIDENCE_THRESHOLD = 0.70


def is_low_confidence(confidence: float, threshold: float = LOW_CONFIDENCE_THRESHOLD) -> bool:
    return confidence < threshold


def worst_field_confidence(field_confidences: list) -> float:
    if not field_confidences:
        return 0.0
    return min(fc.confidence for fc in field_confidences)