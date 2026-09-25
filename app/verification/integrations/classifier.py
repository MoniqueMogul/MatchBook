from __future__ import annotations

import re
from typing import Protocol

from app.db.db_enum import DocumentType
from app.verification.schemas import DetectedDocumentClassification


class DocumentClassifier(Protocol):
    def classify(self, document_text: str) -> DetectedDocumentClassification: ...


class LocalDocumentTypeClassifier:
    """Conservative local classifier that never exports document content."""

    _PRIMARY_MARKERS: dict[DocumentType, tuple[str, ...]] = {
        DocumentType.BANK_STATEMENT: (
            "bank statement",
            "statement of account",
        ),
        DocumentType.TAX_RETURN: (
            "tax return",
            "form 1040",
            "form 1065",
            "form 1120",
            "form 990",
        ),
        DocumentType.PROFIT_AND_LOSS: (
            "profit and loss",
            "income statement",
            "statement of operations",
        ),
        DocumentType.BALANCE_SHEET: ("balance sheet",),
        DocumentType.PROOF_OF_FUNDS: (
            "proof of funds",
            "verification of deposit",
        ),
        DocumentType.LOAN_APPROVAL: (
            "loan approval",
            "loan commitment letter",
        ),
        DocumentType.BUSINESS_LICENSE: (
            "business license",
            "business licence",
        ),
    }

    def classify(self, document_text: str) -> DetectedDocumentClassification:
        normalized = _normalize_text(document_text)
        matches = {
            document_type
            for document_type, markers in self._PRIMARY_MARKERS.items()
            if any(marker in normalized for marker in markers)
        }

        if not matches:
            matches.update(_secondary_matches(normalized))

        if len(matches) != 1:
            return DetectedDocumentClassification(
                detected_type=DocumentType.OTHER,
                confidence=0.0,
            )

        return DetectedDocumentClassification(
            detected_type=matches.pop(),
            confidence=0.95,
        )


def _secondary_matches(normalized: str) -> set[DocumentType]:
    matches: set[DocumentType] = set()
    if all(
        marker in normalized
        for marker in ("account number", "statement period")
    ):
        matches.add(DocumentType.BANK_STATEMENT)
    if all(
        marker in normalized
        for marker in ("assets", "liabilities", "equity")
    ):
        matches.add(DocumentType.BALANCE_SHEET)
    if "pre approval" in normalized and "loan" in normalized:
        matches.add(DocumentType.LOAN_APPROVAL)
    return matches


def _normalize_text(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^a-z0-9]+", " ", value.lower()),
    ).strip()
