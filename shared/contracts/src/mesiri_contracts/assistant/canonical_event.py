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
    GENERAL_QUESTION_ASKED = "GeneralQuestionAsked"
    IDENTITY_LOOKUP_REQUESTED = "IdentityLookupRequested"
    INVENTORY_QUERY_ASKED = "InventoryQueryAsked"
    ACCOUNT_BALANCE_QUERY_ASKED = "AccountBalanceQueryAsked"
    EXPENSE_QUERY_ASKED = "ExpenseQueryAsked"
    # Deterministic (non-AI) command, never produced by canonicalization/
    # extraction -- constructed directly by
    # runtime/account_admin_journey.py when it recognizes a "create/rename/
    # deactivate account" phrase. Present here (rather than skipping the
    # enum) so PlannerDecisionV2.reason and telemetry are accurate.
    ACCOUNT_ADMIN_REQUESTED = "AccountAdminRequested"
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
