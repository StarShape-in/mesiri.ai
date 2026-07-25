"""DraftAction.v1 — the proposed business action a workflow produces, awaiting confirmation.

Produced by the Workflow Runtime (M6) from collected fields. A DraftAction is
the workflow→application handoff: it describes *what would be recorded* if the
user confirms, but nothing is persisted to the domain until confirmation
(architecture rule #4). It carries no domain rules and no SQL knowledge — it is
a pure data description of an intended action.

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v1.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

CONTRACT_VERSION = "v1"


class DraftActionType(str, Enum):
    """The kind of business record a draft would create."""

    RECORD_MATERIAL_RECEIPT = "record_material_receipt"
    RECORD_MATERIAL_USAGE = "record_material_usage"
    RECORD_EXPENSE = "record_expense"
    MANAGE_MONEY_ACCOUNT = "manage_money_account"
    TRANSFER_MONEY = "transfer_money"
    # Future v1 domains: record_equipment_usage, record_labour_attendance


class DraftAction(BaseModel):
    """A proposed business action produced by a workflow, awaiting confirmation."""

    version: str = CONTRACT_VERSION

    # -- Provenance / linkage (correlation must survive end to end) ----------
    draft_id: str
    correlation_id: str
    causation_event_id: str | None = None
    workflow_instance_id: str

    # -- The proposed action -------------------------------------------------
    action_type: DraftActionType

    # -- Tenancy / scope ------------------------------------------------------
    organization_id: str
    user_id: str
    project_id: str | None = None
    site_id: str | None = None

    # -- The structured business payload that would be recorded --------------
    fields: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}
