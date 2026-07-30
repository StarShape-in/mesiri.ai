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
