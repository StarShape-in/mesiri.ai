"""Site Issue Close-out workflow nodes — unit tests (pure functions, no LangGraph needed).

Mirrors test_site_issue_report_nodes.py's pattern, plus the "nothing to
close" no-draft outcome (mirrors workflows/reverse's equivalent test, if any).
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.site_issue_close.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"
ISSUE_ID = "55555555-5555-4555-8555-555555555555"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.SITE_ISSUE_CLOSE.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": PRJ,
        "site_id": SITE,
        "collected_fields": fields,
    }


def test_build_draft_with_a_resolved_target():
    state = _base_state(
        {
            "action": "resolve",
            "site_issue_id": ISSUE_ID,
            "site_issue_type": "MATERIAL_SHORTAGE",
            "site_issue_narrative": "Ran out of cement",
            "resolution_notes": "New delivery arrived",
        }
    )
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.action_type is DraftActionType.CLOSE_SITE_ISSUE
    assert draft.fields == {
        "action": "resolve",
        "site_issue_id": ISSUE_ID,
        "resolution_notes": "New delivery arrived",
    }
    assert draft.organization_id == ORG
    assert draft.project_id == PRJ
    assert draft.site_id == SITE


def test_build_draft_excludes_display_only_fields():
    state = _base_state(
        {
            "action": "acknowledge",
            "site_issue_id": ISSUE_ID,
            "site_issue_type": "WEATHER",
            "site_issue_severity": "HIGH",
            "site_issue_narrative": "Raining",
        }
    )
    draft = build_draft(state)["draft_action"]
    assert "site_issue_type" not in draft.fields
    assert "site_issue_severity" not in draft.fields
    assert "site_issue_narrative" not in draft.fields
    assert draft.fields["site_issue_id"] == ISSUE_ID


def test_build_draft_with_nothing_to_close_returns_no_draft():
    state = _base_state({"action": "resolve"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert update["pending_prompt"] == "You have no open or acknowledged site issues to resolve."


def test_build_draft_nothing_to_acknowledge_uses_acknowledge_specific_message():
    state = _base_state({"action": "acknowledge"})
    update = build_draft(state)
    assert update["pending_prompt"] == "You have no open site issues to acknowledge."


def test_request_confirmation_names_the_action_and_issue():
    state = _base_state(
        {
            "action": "wont_fix",
            "site_issue_id": ISSUE_ID,
            "site_issue_type": "EQUIPMENT_BREAKDOWN",
            "site_issue_narrative": "JCB broke down",
            "resolution_notes": "Not worth repairing",
        }
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Won't Fix" in prompt
    assert "EQUIPMENT_BREAKDOWN" in prompt
    assert "JCB broke down" in prompt
    assert "Not worth repairing" in prompt
    assert "YES" in prompt


def test_request_confirmation_without_notes_omits_notes_line():
    state = _base_state({"action": "acknowledge", "site_issue_id": ISSUE_ID, "site_issue_type": "WEATHER"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Notes:" not in prompt
