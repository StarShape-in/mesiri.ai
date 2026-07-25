"""Structured extraction candidates (M3).

These are *understanding hypotheses*, not authoritative business records. The
understanding pipeline never persists them; downstream context/planner/domain
layers decide truth. Every field is optional so missing information stays
explicitly unknown — the pipeline must never fabricate a value.

Ownership: Ilan (part of UnderstandingResult.v1). CROSS-REVIEW for shape.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .enums import SemanticType


class FieldConfidence(BaseModel):
    """Per-field confidence and provenance for a single extracted value."""

    field: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = None  # provider-provided justification / source span


class Candidate(BaseModel):
    """Base for all extraction candidates.

    ``fields`` holds recognised values; ``unknown_fields`` records keys the
    provider surfaced but the schema does not model; ``missing_fields`` names
    required-but-absent keys; ``field_confidences`` and ``warnings`` carry
    quality signals.
    """

    semantic_type: SemanticType
    fields: dict[str, Any] = Field(default_factory=dict)
    unknown_fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    field_confidences: list[FieldConfidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExpenseCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.EXPENSE
    # Conventional keys (all optional): amount, currency, vendor, category,
    # description, paid_to, occurred_on. Kept in `fields` so the schema stays
    # forgiving while a stable shape emerges.


class EquipmentUsageCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.EQUIPMENT_USAGE
    # Conventional keys: equipment_name, duration_hours, operator, activity.


class MaterialUpdateCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.MATERIAL_UPDATE
    # Conventional keys: material_name, quantity, unit, direction(received/used),
    # work_item (usage only -- the activity the material was used for).


class LabourUpdateCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.LABOUR_UPDATE
    # Conventional keys: headcount, trade, hours, contractor.


class GeneralSiteUpdateCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.GENERAL_SITE_UPDATE
    # Conventional keys: summary, activity, location, weather.


class GeneralQuestionCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.GENERAL_QUESTION
    # Conventional keys: question, topic.


class InventoryQueryCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.INVENTORY_QUERY
    # Conventional keys: material_name (optional -- absent means "all materials").


class FinanceQueryCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.FINANCE_QUERY
    # Conventional keys: query_kind (balance/expenses, required to route --
    # see canonicalization/mapping.py), account_name, category_name,
    # date_range (today/this_week/this_month).


class TransferCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.TRANSFER
    # Conventional keys: amount, from_account_name, to_account_name,
    # description. Account names are best-effort hints -- resolved against
    # the org's real accounts by workflows/transfer/nodes.py, which asks
    # when a name doesn't resolve (see workflows/slots.py).


# Registry so callers can build the right candidate from a semantic type.
CANDIDATE_TYPES: dict[SemanticType, type[Candidate]] = {
    SemanticType.EXPENSE: ExpenseCandidate,
    SemanticType.EQUIPMENT_USAGE: EquipmentUsageCandidate,
    SemanticType.MATERIAL_UPDATE: MaterialUpdateCandidate,
    SemanticType.LABOUR_UPDATE: LabourUpdateCandidate,
    SemanticType.GENERAL_SITE_UPDATE: GeneralSiteUpdateCandidate,
    SemanticType.GENERAL_QUESTION: GeneralQuestionCandidate,
    SemanticType.INVENTORY_QUERY: InventoryQueryCandidate,
    SemanticType.FINANCE_QUERY: FinanceQueryCandidate,
    SemanticType.TRANSFER: TransferCandidate,
}
