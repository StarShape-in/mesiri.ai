"""Context module enumerations (ResolvedContext.v1 + port DTOs).

These classify resolved business context — not workflow selections. The Planner
(M6) owns workflow choice; Context only surfaces what is already active.

Ownership: SHARED ARCHITECTURE — cross-review required.
"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """Canonical Mesiri business roles for resolved actors."""

    OWNER = "owner"
    PROJECT_MANAGER = "project_manager"
    SITE_ENGINEER = "site_engineer"
    ACCOUNTANT = "accountant"
    # Reserved for future modules — not used by Context v1 behaviour.
    SUBCONTRACTOR = "subcontractor"
    STORE_KEEPER = "store_keeper"
    PROCUREMENT_OFFICER = "procurement_officer"
    ADMINISTRATOR = "administrator"


class WorkflowKind(str, Enum):
    """Descriptive label for an *already active* workflow instance.

    Context reports this; it does not select or start workflows.
    """

    MATERIAL = "material"
    WORKFORCE = "workforce"
    EQUIPMENT = "equipment"
    EXPENSE = "expense"
    PROCUREMENT = "procurement"
    UNKNOWN = "unknown"


class WorkflowPhase(str, Enum):
    """Phase of an active workflow instance (read-only snapshot)."""

    ACTIVE = "active"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COLLECTING_FIELDS = "collecting_fields"
    PAUSED = "paused"
    # Terminal outcomes of a human confirmation (M7). CONFIRMED is distinct from
    # COMPLETED: the user approved the draft, but the domain write happens in a
    # later milestone — the workflow is confirmed-and-handed-off, not done.
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    # Domain validation rejected a confirmed draft (M8) — distinct from REJECTED,
    # which means the *user* rejected the draft before execution ever ran.
    # Terminal: the recovery sweep only ever selects phase='confirmed', so this
    # must never be reachable again once set, or a business-rejected workflow
    # would be replayed forever with the same cached rejection.
    EXECUTION_REJECTED = "execution_rejected"
    FAILED = "failed"
    UNKNOWN = "unknown"


class InteractionKind(str, Enum):
    """Kind of a pending human interaction (read-only snapshot)."""

    CONFIRMATION = "confirmation"
    MISSING_FIELD = "missing_field"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


class ContextAmbiguityField(str, Enum):
    """Which part of the resolved context remains ambiguous."""

    USER = "user"
    ORGANIZATION = "organization"
    PROJECT = "project"
    SITE = "site"
    WORKFLOW = "workflow"
    INTERACTION = "interaction"
    CORRELATION = "correlation"
    SCOPE = "scope"
