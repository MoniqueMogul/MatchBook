"""
Flags discrepancies for human review by writing to the shared Event table
(EventType.DISCREPANCY_FLAGGED). Dedicated review-queue table TBD with core team.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_enum import EventType
from app.verification.repositories import events as events_repo


class DiscrepancyType(str, Enum):
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    BUSINESS_NAME_MISMATCH = "BUSINESS_NAME_MISMATCH"
    EIN_MISMATCH = "EIN_MISMATCH"
    OWNERSHIP_AMBIGUITY = "OWNERSHIP_AMBIGUITY"
    REVENUE_DISCREPANCY = "REVENUE_DISCREPANCY"
    SDE_DISCREPANCY = "SDE_DISCREPANCY"
    MISSING_FINANCIAL_RECORDS = "MISSING_FINANCIAL_RECORDS"
    CONFLICTING_EXTERNAL_RECORDS = "CONFLICTING_EXTERNAL_RECORDS"
    LOW_CONFIDENCE_EXTRACTION = "LOW_CONFIDENCE_EXTRACTION"
    UNEXPECTED_FINANCIAL_ACTIVITY = "UNEXPECTED_FINANCIAL_ACTIVITY"


@dataclass
class Discrepancy:
    entity_type: str
    entity_id: UUID
    discrepancy_type: DiscrepancyType
    evidence: dict = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.utcnow)


def flag_for_review(db: Session, discrepancy: Discrepancy) -> None:
    events_repo.publish_event(
        db,
        event_type=EventType.DISCREPANCY_FLAGGED,
        entity_type=discrepancy.entity_type,
        entity_id=discrepancy.entity_id,
        payload={
            "discrepancy_type": discrepancy.discrepancy_type.value,
            "evidence": discrepancy.evidence,
            "detected_at": discrepancy.detected_at.isoformat(),
        },
    )


def low_confidence_discrepancy(entity_type: str, entity_id: UUID, field_name: str, confidence: float, threshold: float) -> Discrepancy:
    return Discrepancy(
        entity_type=entity_type,
        entity_id=entity_id,
        discrepancy_type=DiscrepancyType.LOW_CONFIDENCE_EXTRACTION,
        evidence={"field": field_name, "confidence": confidence, "threshold": threshold},
    )


def financial_mismatch_discrepancy(entity_type: str, entity_id: UUID, field_name: str, reported_value, authoritative_value, difference_pct) -> Discrepancy:
    discrepancy_type = DiscrepancyType.REVENUE_DISCREPANCY if field_name == "arr" else DiscrepancyType.SDE_DISCREPANCY
    return Discrepancy(
        entity_type=entity_type,
        entity_id=entity_id,
        discrepancy_type=discrepancy_type,
        evidence={
            "field": field_name,
            "reported_value": reported_value,
            "authoritative_value": authoritative_value,
            "difference_pct": difference_pct,
        },
    )