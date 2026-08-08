"""Site Issue Report workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.site_issue_report.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.SITE_ISSUE_REPORT.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": PRJ,
        "site_id": SITE,
        "collected_fields": fields,
    }


def test_build_draft_site_issue():
    state = _base_state(
        {"issue_type": "MATERIAL_SHORTAGE", "severity": "HIGH", "narrative": "Ran out of cement"}
    )
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.action_type is DraftActionType.RECORD_SITE_ISSUE
    assert draft.fields == {
        "issue_type": "MATERIAL_SHORTAGE",
        "severity": "HIGH",
        "narrative": "Ran out of cement",
    }
    assert draft.workflow_instance_id == "wf_1"
    assert draft.correlation_id == "cor_1"
    assert draft.organization_id == ORG
    assert draft.project_id == PRJ
    assert draft.site_id == SITE


def test_build_draft_missing_collected_fields_defaults_empty():
    state = _base_state({})
    del state["collected_fields"]
    update = build_draft(state)
    assert update["draft_action"].fields == {}


def test_request_confirmation_sets_prompt_from_draft():
    state = _base_state({"issue_type": "EQUIPMENT_BREAKDOWN", "narrative": "JCB broke down"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Site Issue" in prompt
    assert "EQUIPMENT_BREAKDOWN" in prompt
    assert "JCB broke down" in prompt
    assert "YES" in prompt


def test_request_confirmation_shows_assumed_today_date_note():
    state = _base_state(
        {
            "issue_type": "WEATHER",
            "occurred_date": "2026-07-20",
            "occurred_date_source": "inferred_at_confirmation",
        }
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "assumed today" in prompt
    # The raw occurred_date/occurred_date_source keys must not also appear
    # as generic "key: value" lines -- _date_line is the only place they render.
    assert "occurred_date:" not in prompt
    assert "occurred_date_source:" not in prompt


def test_request_confirmation_shows_stated_date_without_assumed_note():
    state = _base_state({"issue_type": "WEATHER", "occurred_date": "2026-07-19"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "19 Jul 2026" in prompt
    assert "assumed today" not in prompt
