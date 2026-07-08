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
