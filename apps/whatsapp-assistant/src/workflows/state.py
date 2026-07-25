"""The generic LangGraph working-state shape shared by all v1 workflow graphs.

Kept separate from the WorkflowState.v1 contract — this is LangGraph's
in-process working state; WorkflowRuntime converts it to/from WorkflowState.v1
at the boundary. Every v1 graph (material, and later expense/equipment/labour)
starts from this same shape, since the Workflow Runtime always seeds it from
a CanonicalEvent the same way regardless of domain.
"""

from __future__ import annotations

from typing import Any, TypedDict

from mesiri_contracts.assistant.draft_action import DraftAction


class WorkflowGraphState(TypedDict, total=False):
    workflow_instance_id: str
    workflow_key: str
    correlation_id: str
    organization_id: str
    user_id: str
    project_id: str | None
    site_id: str | None
    collected_fields: dict[str, Any]
    draft_action: DraftAction | None
    pending_prompt: str | None
    # Set by a node (e.g. expense_capture's resolve_account) when a
    # single-choice field has more than one candidate and needs the user to
    # pick -- see workflows/slots.py. None means "not currently asking
    # anything" (resolved, or the field had 0/1 candidates).
    awaiting_slot: str | None
