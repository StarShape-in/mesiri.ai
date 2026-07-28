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
    # description, paid_to, occurred_on, tax_rate, tax_amount,
    # is_tax_inclusive (pure preservation of what a bill/receipt states --
    # see backend's application/expenses/commands.py docstring, never
    # computed or validated). Kept in `fields` so the schema stays forgiving
    # while a stable shape emerges.


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


class LabourQueryCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.LABOUR_QUERY
    # Conventional keys: date_range (today/this_week/this_month), trade
    # (optional -- absent means "all trades"). Read-only; carries no business
    # record, only a question to answer.


class GeneralSiteUpdateCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.GENERAL_SITE_UPDATE
    # Conventional keys: summary, activity, location, weather.


class SiteIssueCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.SITE_ISSUE
    # Conventional keys: issue_type (required to route -- see
    # canonicalization/mapping.py; one of WEATHER/MATERIAL_SHORTAGE/
    # LABOUR_SHORTAGE/DRAWING_PENDING/EQUIPMENT_BREAKDOWN/
    # INSPECTION_WAITING/ACCESS/OTHER), severity (LOW/MEDIUM/HIGH/CRITICAL),
    # narrative, delay_duration_minutes, occurred_on. A reported blocker/
    # delay -- never a question about existing ones (that's activity_query).


class SiteIssueUpdateCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.SITE_ISSUE_UPDATE
    # Conventional keys: action (required to route -- see
    # canonicalization/mapping.py; one of acknowledge/resolve/wont_fix),
    # resolution_notes. Always targets the most recently reported issue in
    # the right status, resolved by seeding -- never a new report (that's
    # site_issue).


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


class PettyCashCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.PETTY_CASH
    # Conventional keys: amount, recipient_name, direction (issue/return),
    # description. recipient_name is a best-effort hint -- resolved against
    # the org's real users by runtime/petty_cash_query.py, which auto-
    # creates the recipient's employee-advance account on first issuance
    # (see workflows/petty_cash/nodes.py).


class ReversalCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.REVERSAL
    # Conventional keys: target_kind (expense/transfer, required to route --
    # see canonicalization/mapping.py). No amount/reference fields -- the
    # target is always "the most recent one of this kind", resolved by
    # runtime/reversal_query.py, not stated by the user.


class AccountAdminCandidate(Candidate):
    semantic_type: SemanticType = SemanticType.ACCOUNT_ADMIN
    # Conventional keys: action (create/rename/deactivate, required to
    # route -- see canonicalization/mapping.py), name (create), target_name
    # (rename/deactivate), new_name (rename), account_type (create only,
    # cash/bank). target_name/new_name/name are best-effort hints as stated
    # -- resolved against the org's actual accounts by
    # application/finance/resolution.py, exactly as the deterministic
    # regex-parsed path already worked. ADMIN/FINANCE only -- see
    # runtime/inbound_journey.py and application/finance/validation.py.


# Registry so callers can build the right candidate from a semantic type.
CANDIDATE_TYPES: dict[SemanticType, type[Candidate]] = {
    SemanticType.EXPENSE: ExpenseCandidate,
    SemanticType.EQUIPMENT_USAGE: EquipmentUsageCandidate,
    SemanticType.MATERIAL_UPDATE: MaterialUpdateCandidate,
    SemanticType.LABOUR_UPDATE: LabourUpdateCandidate,
    SemanticType.GENERAL_SITE_UPDATE: GeneralSiteUpdateCandidate,
    SemanticType.SITE_ISSUE: SiteIssueCandidate,
    SemanticType.SITE_ISSUE_UPDATE: SiteIssueUpdateCandidate,
    SemanticType.GENERAL_QUESTION: GeneralQuestionCandidate,
    SemanticType.INVENTORY_QUERY: InventoryQueryCandidate,
    SemanticType.LABOUR_QUERY: LabourQueryCandidate,
    SemanticType.FINANCE_QUERY: FinanceQueryCandidate,
    SemanticType.TRANSFER: TransferCandidate,
    SemanticType.PETTY_CASH: PettyCashCandidate,
    SemanticType.REVERSAL: ReversalCandidate,
    SemanticType.ACCOUNT_ADMIN: AccountAdminCandidate,
}
