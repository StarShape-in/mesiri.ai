"""CanonicalEvent.v1 — the normalized business-intent signal between Context and Planner.

Produced by the canonicalization layer from an ``UnderstandingResult`` +
``ResolvedContext``. A CanonicalEvent is an internal orchestration signal, not a
confirmed fact — e.g. ``MaterialReceiptRequested`` means "the assistant believes
the user wants to record a material receipt." The user may still correct it, the
workflow may reject it, authorization may fail. This is never a ``DomainEvent``
(a confirmed fact, published only after commit).

Per the architecture's layer-ownership table, CanonicalEvent normalizes AI
output into business intent but must never carry knowledge of AI providers or
confidence scores. ``completeness`` is therefore a business-level judgement
(are the required fields present?) — the raw M3 ``ConfidenceLevel`` is
deliberately not represented here.

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v1.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

CONTRACT_VERSION = "v1"


class CanonicalEventType(str, Enum):
    """The normalized business intent the assistant believes the user expressed."""

    MATERIAL_RECEIPT_REQUESTED = "MaterialReceiptRequested"
    MATERIAL_USAGE_REQUESTED = "MaterialUsageRequested"
    EXPENSE_REQUESTED = "ExpenseRequested"
    EQUIPMENT_USAGE_REQUESTED = "EquipmentUsageRequested"
    LABOUR_ATTENDANCE_REQUESTED = "LabourAttendanceRequested"
    GENERAL_SITE_UPDATE_REQUESTED = "GeneralSiteUpdateRequested"
    # GENERAL_SITE_UPDATE splits into this or the above by the extracted
    # `update_kind` field (PROGRESS/PAUSED/RESUMED/COMPLETED -> continuation;
    # absent/STARTED -> a new activity) -- same pattern as MATERIAL_UPDATE's
    # `direction` split (see canonicalization/mapping.py's resolve_event_type).
    ACTIVITY_CONTINUATION_REQUESTED = "ActivityContinuationRequested"
    # SemanticType.SITE_ISSUE -> a reported blocker/delay, always a new
    # site_issues row (no continuation split like GENERAL_SITE_UPDATE has --
    # each report is its own record, never appended to a prior one).
    SITE_ISSUE_REPORTED = "SiteIssueReported"
    # SemanticType.SITE_ISSUE_UPDATE split by the extracted `action` field --
    # same pattern EXPENSE_REVERSAL_REQUESTED/TRANSFER_REVERSAL_REQUESTED
    # use for `target_kind` below. All three route to the single
    # WorkflowKey.SITE_ISSUE_CLOSE (see planner/routing.py).
    SITE_ISSUE_ACKNOWLEDGE_REQUESTED = "SiteIssueAcknowledgeRequested"
    SITE_ISSUE_RESOLVE_REQUESTED = "SiteIssueResolveRequested"
    SITE_ISSUE_WONT_FIX_REQUESTED = "SiteIssueWontFixRequested"
    GENERAL_QUESTION_ASKED = "GeneralQuestionAsked"
    IDENTITY_LOOKUP_REQUESTED = "IdentityLookupRequested"
    INVENTORY_QUERY_ASKED = "InventoryQueryAsked"
    LABOUR_QUERY_ASKED = "LabourQueryAsked"
    ACTIVITY_QUERY_ASKED = "ActivityQueryAsked"
    DPR_REQUESTED = "DprRequested"
    ACCOUNT_BALANCE_QUERY_ASKED = "AccountBalanceQueryAsked"
    EXPENSE_QUERY_ASKED = "ExpenseQueryAsked"
    TRANSFER_REQUESTED = "TransferRequested"
    PETTY_CASH_ISSUE_REQUESTED = "PettyCashIssueRequested"
    PETTY_CASH_RETURN_REQUESTED = "PettyCashReturnRequested"
    EXPENSE_REVERSAL_REQUESTED = "ExpenseReversalRequested"
    TRANSFER_REVERSAL_REQUESTED = "TransferReversalRequested"
    # "create/rename/deactivate account". Two producers as of 2026-07-26:
    # runtime/account_admin_journey.py constructs this directly (zero-token
    # fast path) when its regex parser recognizes the exact phrasing;
    # canonicalization/mapping.py's resolve_event_type also maps
    # SemanticType.ACCOUNT_ADMIN here for everything else (other phrasing,
    # voice, non-English) the AI pipeline understood. Both converge on the
    # same WorkflowKey.ACCOUNT_ADMIN graph and the same role enforcement.
    ACCOUNT_ADMIN_REQUESTED = "AccountAdminRequested"
    # SemanticType.PROJECT_CREATE -> a new project record. No candidate-field
    # split (unlike MATERIAL_UPDATE/PETTY_CASH/REVERSAL/SITE_ISSUE_UPDATE
    # above) since there is only one action (create).
    PROJECT_CREATE_REQUESTED = "ProjectCreateRequested"
    # SemanticType.SITE_CREATE -> a new site record under the project
    # resolved by context (see enums.py's docstring on that type).
    SITE_CREATE_REQUESTED = "SiteCreateRequested"
    # SemanticType.PROJECT_DETAIL_QUERY -> a read-only project/site summary.
    PROJECT_DETAIL_QUERY_ASKED = "ProjectDetailQueryAsked"
    CLARIFICATION_REQUIRED = "ClarificationRequired"
    UNRECOGNIZED = "Unrecognized"


class IntentCompleteness(str, Enum):
    """Business-level completeness of the intent — not an AI confidence score."""

    ACTIONABLE = "actionable"
    NEEDS_CLARIFICATION = "needs_clarification"
    NOT_ACTIONABLE = "not_actionable"


class CanonicalEvent(BaseModel):
    """The normalized business-intent signal consumed by the Planner."""

    version: str = CONTRACT_VERSION

    # -- Provenance / linkage (correlation must survive end to end) ----------
    event_id: str
    correlation_id: str
    source_message_id: str
    causation_id: str | None = None
    conversation_id: str | None = None

    # -- Normalized intent ----------------------------------------------------
    event_type: CanonicalEventType
    completeness: IntentCompleteness

    # -- Tenancy / scope (denormalized from ResolvedContext) ------------------
    organization_id: str
    user_id: str
    project_id: str | None = None
    site_id: str | None = None
    permissions: list[str] = Field(default_factory=list)

    # -- Business intent payload (provider-agnostic) --------------------------
    fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
