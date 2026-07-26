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
from workflows.slots import SlotCandidate

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


def test_awaiting_input_reply_has_no_buttons():
    """Mid-workflow slot question ("which account?") renders prompt without Yes/No buttons."""
    result = WorkflowRunResult.awaiting_input(
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        pending_prompt="Which account would you like to pay from?\n1. Site Cash\n2. Own Pocket",
    )
    reply = _render_reply(result, None, None, None)
    assert reply is not None
    assert reply.text == "Which account would you like to pay from?\n1. Site Cash\n2. Own Pocket"
    assert reply.buttons is None


def test_awaiting_input_with_slot_options_becomes_a_real_interactive_list():
    """A node that supplied candidates (workflows/slots.py's slot_options)
    gets a tappable WhatsApp list, not just numbered text -- the fix for
    the "most messages tell you to type instead of using WhatsApp's
    interactive buttons/lists" gap."""
    result = WorkflowRunResult.awaiting_input(
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        pending_prompt="Which account did you pay from?\n1. Site Cash\n2. Own Pocket",
        slot_options=(
            SlotCandidate(value="acc_1", label="Site Cash"),
            SlotCandidate(value="own_pocket", label="Own Pocket"),
        ),
    )
    reply = _render_reply(result, None, None, None)
    assert reply is not None
    assert reply.buttons is None
    assert reply.list_rows is not None
    assert [row.id for row in reply.list_rows] == ["acc_1", "own_pocket"]
    assert [row.title for row in reply.list_rows] == ["Site Cash", "Own Pocket"]
    assert reply.list_button_label == "Choose one"


def test_awaiting_input_with_a_single_slot_option_falls_back_to_text():
    """A list needs at least 2 real choices -- resolve_single_choice_slot
    never asks with fewer than 2 candidates, but this guards the render
    side defensively too rather than sending WhatsApp a 1-row list."""
    result = WorkflowRunResult.awaiting_input(
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        pending_prompt="Which account did you pay from?",
        slot_options=(SlotCandidate(value="acc_1", label="Site Cash"),),
    )
    reply = _render_reply(result, None, None, None)
    assert reply is not None
    assert reply.list_rows is None


def test_awaiting_input_with_too_many_options_falls_back_to_text():
    """WhatsApp caps an interactive list at 10 rows -- more than that must
    degrade to plain (still typeable) text instead of a request Meta
    would reject outright."""
    options = tuple(SlotCandidate(value=f"acc_{i}", label=f"Account {i}") for i in range(11))
    result = WorkflowRunResult.awaiting_input(
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        pending_prompt="Which account did you pay from?",
        slot_options=options,
    )
    reply = _render_reply(result, None, None, None)
    assert reply is not None
    assert reply.list_rows is None


def test_awaiting_input_with_a_too_long_label_falls_back_to_text():
    """WhatsApp caps a list row title at 24 characters."""
    options = (
        SlotCandidate(value="acc_1", label="A Very Long Account Name That Exceeds Limits"),
        SlotCandidate(value="acc_2", label="Site Cash"),
    )
    result = WorkflowRunResult.awaiting_input(
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        pending_prompt="Which account did you pay from?",
        slot_options=options,
    )
    reply = _render_reply(result, None, None, None)
    assert reply is not None
    assert reply.list_rows is None

