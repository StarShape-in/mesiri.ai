"""WorkflowState.v1 — the durable, resumable snapshot of a workflow instance.

Serialized into `workflow_instances.state` (JSONB) by a repository adapter.
This is the *single durable source of truth* for a running workflow — LangGraph
itself runs without a checkpointer in M6 (no pause/resume inside LangGraph
yet); resumption is driven by loading this snapshot back, not by LangGraph
internals. LangGraph never touches this table directly (architecture rule #11:
"LangGraph never imports SQL, Postgres, or a repository") — only the Workflow
Runtime reads/writes it, through the repository port.

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v1.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mesiri_contracts.context.enums import WorkflowPhase

from .draft_action import DraftAction
from .planner_decision import WorkflowKey

CONTRACT_VERSION = "v1"


class WorkflowState(BaseModel):
    """The durable snapshot of one running workflow instance."""

    version: str = CONTRACT_VERSION

    # -- Identity / linkage ---------------------------------------------------
    workflow_instance_id: str
    workflow_key: WorkflowKey
    correlation_id: str

    # -- Tenancy / scope ------------------------------------------------------
    organization_id: str
    user_id: str
    project_id: str | None = None
    site_id: str | None = None

    # -- State ------------------------------------------------------------
    phase: WorkflowPhase = WorkflowPhase.ACTIVE
    collected_fields: dict[str, Any] = Field(default_factory=dict)
    draft_action: DraftAction | None = None
    pending_prompt: str | None = None

    model_config = {"extra": "forbid"}
