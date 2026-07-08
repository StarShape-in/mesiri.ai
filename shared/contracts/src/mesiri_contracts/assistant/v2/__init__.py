"""Assistant contracts v2 — canonical Control Plane UUID scope IDs."""

from mesiri_contracts.assistant.v2.canonical_event import (
    CONTRACT_VERSION as CANONICAL_EVENT_V2_VERSION,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.draft_action import (
    CONTRACT_VERSION as DRAFT_ACTION_V2_VERSION,
)
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.planner_decision import (
    CONTRACT_VERSION as PLANNER_DECISION_V2_VERSION,
)
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.resolved_context import (
    CONTRACT_VERSION as RESOLVED_CONTEXT_V2_VERSION,
)
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from mesiri_contracts.assistant.v2.workflow_state import (
    CONTRACT_VERSION as WORKFLOW_STATE_V2_VERSION,
)
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2

__all__ = [
    "ResolvedContextV2",
    "RESOLVED_CONTEXT_V2_VERSION",
    "CanonicalEventV2",
    "CANONICAL_EVENT_V2_VERSION",
    "PlannerDecisionV2",
    "PLANNER_DECISION_V2_VERSION",
    "WorkflowStateV2",
    "WORKFLOW_STATE_V2_VERSION",
    "DraftActionV2",
    "DRAFT_ACTION_V2_VERSION",
]
