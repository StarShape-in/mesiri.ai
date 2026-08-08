"""ConfirmedAction.v2 — a draft the user confirmed; the M7 -> Application handoff.

Produced by the Workflow Runtime when a user confirms an AWAITING_CONFIRMATION
workflow (M7). It is the gated handoff to the future Application/Domain layer:
domain validation, idempotent command execution, and persistence happen there,
not here. Carries the confirmed DraftActionV2 plus who confirmed it. No
timestamp — the Application layer stamps time on execution, consistent with the
other assistant contracts.

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v2.
"""

from __future__ import annotations

from pydantic import BaseModel

from .draft_action import DraftActionV2
from .uuid_scope import CanonicalUuid

CONTRACT_VERSION = "v2"


class ConfirmedActionV2(BaseModel):
    """A confirmed draft action, ready for the Application layer to execute."""

    version: str = CONTRACT_VERSION

    confirmed_action_id: str
    workflow_instance_id: str
    correlation_id: str

    draft_action: DraftActionV2
    confirmed_by_user_id: CanonicalUuid

    model_config = {"extra": "forbid"}
