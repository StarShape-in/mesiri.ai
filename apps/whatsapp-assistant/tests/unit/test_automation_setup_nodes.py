"""Automation setup workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.automation_setup.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
PROJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict, project_id: str | None = None, site_id: str | None = None) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.AUTOMATION_SETUP.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": project_id,
        "site_id": site_id,
        "collected_fields": fields,
    }


def test_missing_time_of_day_asks_instead_of_building_a_draft():
    state = _base_state({"automation_action": "REMINDER", "message": "hi"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "what time" in update["pending_prompt"].lower()


def test_build_draft_defaults_to_self_reminder_when_message_given():
    state = _base_state({"time_of_day": "17:00", "message": "please submit your DPR"})
    draft = build_draft(state)["draft_action"]
    assert draft.action_type is DraftActionType.CREATE_AUTOMATION
    assert draft.fields["action"] == "REMINDER"
    assert draft.fields["audience"] == "SELF"
    assert draft.fields["frequency"] == "DAILY"


def test_build_draft_defaults_to_send_dpr_when_no_message():
    state = _base_state({"time_of_day": "17:00"}, site_id="44444444-4444-4444-8444-444444444444")
    draft = build_draft(state)["draft_action"]
    assert draft.fields["action"] == "SEND_DPR"


def test_build_draft_translates_automation_action_field_name():
    state = _base_state({"time_of_day": "15:00", "automation_action": "COMPLIANCE_SUMMARY"})
    draft = build_draft(state)["draft_action"]
    assert draft.fields["action"] == "COMPLIANCE_SUMMARY"
    assert "automation_action" not in draft.fields


def test_build_draft_infers_users_audience_from_audience_names():
    state = _base_state(
        {"time_of_day": "18:00", "audience_names": ["Ilan", "Hysam"], "message": "please submit"}
    )
    draft = build_draft(state)["draft_action"]
    assert draft.fields["audience"] == "USERS"
    assert draft.fields["audience_names"] == ["Ilan", "Hysam"]


def test_build_draft_infers_role_audience_from_audience_role():
    state = _base_state(
        {"time_of_day": "18:00", "audience_role": "SITE_ENGINEER", "message": "please submit"}
    )
    draft = build_draft(state)["draft_action"]
    assert draft.fields["audience"] == "ROLE"


def test_build_draft_converts_weekday_name_to_int():
    state = _base_state(
        {
            "time_of_day": "09:00",
            "frequency": "WEEKLY",
            "day_of_week": "Monday",
            "message": "hi",
        }
    )
    draft = build_draft(state)["draft_action"]
    assert draft.fields["day_of_week"] == 0
    assert draft.fields["frequency"] == "WEEKLY"


def test_build_draft_drops_unrecognised_weekday_name():
    state = _base_state(
        {
            "time_of_day": "09:00",
            "frequency": "WEEKLY",
            "day_of_week": "Blursday",
            "message": "hi",
        }
    )
    draft = build_draft(state)["draft_action"]
    assert "day_of_week" not in draft.fields


def test_build_draft_carries_project_and_site_scope():
    state = _base_state({"time_of_day": "17:00"}, project_id=PROJ, site_id="44444444-4444-4444-8444-444444444444")
    draft = build_draft(state)["draft_action"]
    assert draft.project_id == PROJ
    assert draft.site_id == "44444444-4444-4444-8444-444444444444"


def test_request_confirmation_prompt_for_self_dpr():
    state = _base_state({"time_of_day": "17:00"}, site_id="44444444-4444-4444-8444-444444444444")
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "17:00" in prompt
    assert "every day" in prompt.lower()
    assert "YES" in prompt


def test_request_confirmation_prompt_shows_named_audience():
    state = _base_state(
        {"time_of_day": "18:00", "audience_names": ["Ilan", "Hysam"], "message": "please submit"}
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Ilan" in prompt
    assert "Hysam" in prompt
    assert "please submit" in prompt


def test_request_confirmation_prompt_shows_weekly_day_name():
    state = _base_state(
        {
            "time_of_day": "09:00",
            "frequency": "WEEKLY",
            "day_of_week": "Monday",
            "message": "hi",
        }
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Monday" in prompt
