"""Create-user workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.create_user.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.CREATE_USER.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


def test_build_draft_with_name_and_number_defaults_role():
    state = _base_state({"full_name": "Rajesh", "whatsapp_number": "919876543210"})
    draft = build_draft(state)["draft_action"]
    assert draft.action_type is DraftActionType.CREATE_USER
    assert draft.project_id is None
    assert draft.fields["full_name"] == "Rajesh"
    assert draft.fields["role"] == "SITE_ENGINEER"


def test_build_draft_normalizes_the_phone_number_to_digits_only():
    state = _base_state({"full_name": "Rajesh", "whatsapp_number": "+91 98765-43210"})
    draft = build_draft(state)["draft_action"]
    assert draft.fields["whatsapp_number"] == "919876543210"


def test_build_draft_normalizes_role_hint():
    state = _base_state(
        {"full_name": "Priya", "whatsapp_number": "9876543210", "role": "project manager"}
    )
    draft = build_draft(state)["draft_action"]
    assert draft.fields["role"] == "PROJECT_MANAGER"


def test_build_draft_carries_created_by_role():
    state = _base_state(
        {
            "full_name": "Rajesh",
            "whatsapp_number": "9876543210",
            "created_by_role": "ADMIN",
        }
    )
    draft = build_draft(state)["draft_action"]
    assert draft.fields["created_by_role"] == "ADMIN"


def test_request_confirmation_prompt_calls_out_the_number():
    state = _base_state({"full_name": "Rajesh", "whatsapp_number": "9876543210"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Rajesh" in prompt
    assert "9876543210" in prompt
    assert "double check" in prompt.lower()
    assert "Site Engineer" in prompt
    assert "YES" in prompt


def test_build_draft_missing_name_asks_instead_of_building_an_incomplete_draft():
    state = _base_state({"whatsapp_number": "9876543210"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "name" in update["pending_prompt"].lower()


def test_build_draft_missing_number_asks_instead_of_building_an_incomplete_draft():
    state = _base_state({"full_name": "Rajesh"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "number" in update["pending_prompt"].lower()


def test_build_draft_too_short_a_number_asks_to_resend_rather_than_guessing():
    state = _base_state({"full_name": "Rajesh", "whatsapp_number": "123"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "valid" in update["pending_prompt"].lower()


def test_build_draft_missing_name_takes_priority_over_missing_number():
    state = _base_state({})
    update = build_draft(state)
    assert "name" in update["pending_prompt"].lower()


# ---------------------------------------------------------------------------
# resolve_whatsapp_number -- the slot-fill node (ENTITY_RESOLUTION_PLAN.md's
# CREATE_USER -> ADD_PROJECT_MEMBER chain starts this workflow with a name
# and no number; without a real awaiting_slot, the number reply was lost --
# confirmed by a live trace, not a hypothetical).
# ---------------------------------------------------------------------------

from workflows.create_user.nodes import _NUMBER_SLOT_NAME, resolve_whatsapp_number


def test_resolve_number_first_pass_with_a_valid_number_resolves_silently():
    state = _base_state({"full_name": "Rajesh", "whatsapp_number": "919876543210"})
    update = resolve_whatsapp_number(state)
    assert update["awaiting_slot"] is None
    assert update["collected_fields"]["whatsapp_number"] == "919876543210"


def test_resolve_number_first_pass_with_no_number_sets_awaiting_slot():
    state = _base_state({"full_name": "Hysam"})
    update = resolve_whatsapp_number(state)
    assert update["awaiting_slot"] == _NUMBER_SLOT_NAME
    assert "number" in update["pending_prompt"].lower()


def test_resolve_number_first_pass_with_an_invalid_number_sets_awaiting_slot():
    state = _base_state({"full_name": "Hysam", "whatsapp_number": "123"})
    update = resolve_whatsapp_number(state)
    assert update["awaiting_slot"] == _NUMBER_SLOT_NAME
    assert "valid" in update["pending_prompt"].lower()


def test_resolve_number_no_name_yet_is_a_no_op_deferring_to_build_draft():
    """The name field keeps its old single-message-retry behaviour --
    only the number becomes a real slot."""
    state = _base_state({"whatsapp_number": "919876543210"})
    assert resolve_whatsapp_number(state) == {}


def test_resolve_number_slot_answer_with_a_valid_number_resolves_and_clears_slot():
    """Simulates WorkflowRuntime.provide_input's re-invocation: the state
    carries _slot_answer_text (the user's reply) and the awaiting_slot that
    was pending."""
    state = _base_state({"full_name": "Hysam", "_slot_answer_text": "+91 97781 90485"})
    state["awaiting_slot"] = _NUMBER_SLOT_NAME
    update = resolve_whatsapp_number(state)
    assert update["awaiting_slot"] is None
    assert update["collected_fields"]["whatsapp_number"] == "919778190485"
    assert "_slot_answer_text" not in update["collected_fields"]


def test_resolve_number_slot_answer_with_an_invalid_number_reasks():
    state = _base_state({"full_name": "Hysam", "_slot_answer_text": "abc"})
    state["awaiting_slot"] = _NUMBER_SLOT_NAME
    update = resolve_whatsapp_number(state)
    assert update["awaiting_slot"] == _NUMBER_SLOT_NAME
    assert "valid" in update["pending_prompt"].lower()
