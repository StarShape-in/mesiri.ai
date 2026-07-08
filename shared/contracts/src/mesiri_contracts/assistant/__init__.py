"""Assistant-facing shared contracts."""

from mesiri_contracts.assistant.canonical_event import (
    CONTRACT_VERSION as CANONICAL_EVENT_VERSION,
)
from mesiri_contracts.assistant.canonical_event import (
    CanonicalEvent,
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.draft_action import (
    CONTRACT_VERSION as DRAFT_ACTION_VERSION,
)
from mesiri_contracts.assistant.draft_action import DraftAction, DraftActionType
from mesiri_contracts.assistant.normalized_message import (
    MediaReference,
    NormalizedMessage,
    ReplyContext,
    SenderInfo,
)
from mesiri_contracts.assistant.planner_decision import (
    CONTRACT_VERSION as PLANNER_DECISION_VERSION,
)
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecision,
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)
from mesiri_contracts.assistant.resolved_context import (
    CONTRACT_VERSION as RESOLVED_CONTEXT_VERSION,
)
from mesiri_contracts.assistant.resolved_context import ResolvedContext
from mesiri_contracts.assistant.workflow_state import (
    CONTRACT_VERSION as WORKFLOW_STATE_VERSION,
)
from mesiri_contracts.assistant.workflow_state import WorkflowState

from mesiri_contracts.assistant import v2 as assistant_v2

__all__ = [
    "MediaReference",
    "NormalizedMessage",
    "ReplyContext",
    "SenderInfo",
    "ResolvedContext",
    "ContextSource",
    "ContextConfidence",
    "RESOLVED_CONTEXT_VERSION",
    "CanonicalEvent",
    "CanonicalEventType",
    "IntentCompleteness",
    "CANONICAL_EVENT_VERSION",
    "PlannerDecision",
    "PlannerDecisionType",
    "PlannerPriority",
    "WorkflowKey",
    "PLANNER_DECISION_VERSION",
    "DraftAction",
    "DraftActionType",
    "DRAFT_ACTION_VERSION",
    "WorkflowState",
    "WORKFLOW_STATE_VERSION",
    "assistant_v2",
]
