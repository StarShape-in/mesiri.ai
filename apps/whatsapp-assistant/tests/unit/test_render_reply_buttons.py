"""Unit tests for runtime.inbound_journey._render_reply's button vs plain-text split.

A confirmation prompt (STARTED, or an old one re-shown via
BLOCKED_PENDING_CONFIRMATION) must carry Yes/No buttons. An informational
reply with nothing to confirm (COMPLETED -- who_am_i, inventory_query) must
stay plain text; showing Yes/No under an answer that was never asking a
question would be actively confusing.
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from runtime.inbound_journey import _render_reply
from workflows import WorkflowRunResult

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _draft() -> DraftActionV2:
    return DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "cement", "quantity": 50, "unit": "bags"},
    )


def test_started_confirmation_carries_yes_no_buttons():
    result = WorkflowRunResult.started(
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        draft_action=_draft(),
        pending_prompt="*Confirm this record?*",
    )
    reply = _render_reply(result, None, None, None)
    assert reply is not None
    assert reply.buttons is not None
    assert [b.id for b in reply.buttons] == ["confirm_yes", "confirm_no"]


def test_blocked_pending_confirmation_also_carries_buttons():
    """The "please finish the pending confirmation first" re-show is still
    asking the user to confirm something -- it needs buttons too."""
    result = WorkflowRunResult.blocked_pending_confirmation(
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="cor_1",
        pending_prompt="*Confirm this record?*",
    )
    reply = _render_reply(result, None, None, None)
    assert reply is not None
    assert reply.buttons is not None


def test_completed_informational_reply_has_no_buttons():
    """who_am_i / inventory_query answers are not a question -- no Yes/No."""
    result = WorkflowRunResult.completed(
        workflow_key=WorkflowKey.WHO_AM_I,
        correlation_id="cor_1",
        pending_prompt="Here is your profile...",
    )
    reply = _render_reply(result, None, None, None)
    assert reply is not None
    assert reply.buttons is None
