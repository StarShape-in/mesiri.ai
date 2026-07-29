"""Activity Quantity Correction workflow nodes — unit tests (pure functions, no LangGraph needed).

ADR-D14: "make that 180 sqm" -- see module docstring in
workflows/activity_correction/nodes.py for what this replaces (the old
create-vs-continue-only model had no correction path at all).
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.activity_correction.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PROGRESS_UPDATE_ID = "55555555-5555-4555-8555-555555555555"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.ACTIVITY_CORRECTION.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


def test_builds_a_draft_when_a_target_was_seeded():
    state = _base_state(
        {
            "progress_update_id": PROGRESS_UPDATE_ID,
            "new_quantity": 180,
            "unit": "sqm",
            "old_quantity": "80",
            "old_unit": "sqm",
            "correction_activity_summary": "plastering — 2nd floor",
        }
    )
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.action_type is DraftActionType.CORRECT_ACTIVITY_QUANTITY
    assert draft.fields["progress_update_id"] == PROGRESS_UPDATE_ID
    assert draft.fields["new_quantity"] == 180
    assert draft.fields["unit"] == "sqm"


def test_no_new_unit_stated_falls_back_to_the_original_unit():
    """"Make that 180" with no unit restated -- assume the same unit the
    original quantity was in, since a correction almost never also changes
    the unit of measure."""
    state = _base_state(
        {
            "progress_update_id": PROGRESS_UPDATE_ID,
            "new_quantity": 180,
            "old_quantity": "80",
            "old_unit": "sqm",
        }
    )
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.fields["unit"] == "sqm"


def test_no_target_seeded_completes_without_a_draft():
    """No same-session activity/progress-update to correct (see
    runtime/inbound_journey.py's _seed_correction_target docstring) -- a
    friendly reply, not a dead end."""
    state = _base_state({"new_quantity": 180, "unit": "sqm"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "don't see anything you just logged" in update["pending_prompt"]


def test_request_confirmation_shows_old_value_arrow_new_value():
    state = _base_state(
        {
            "progress_update_id": PROGRESS_UPDATE_ID,
            "new_quantity": 180,
            "unit": "sqm",
            "old_quantity": "80",
            "old_unit": "sqm",
            "correction_activity_summary": "plastering — 2nd floor",
        }
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "plastering — 2nd floor" in prompt
    assert "80 sqm → 180 sqm" in prompt
    assert "YES" in prompt


def test_request_confirmation_shows_reason_when_given():
    state = _base_state(
        {
            "progress_update_id": PROGRESS_UPDATE_ID,
            "new_quantity": 180,
            "unit": "sqm",
            "old_quantity": "80",
            "old_unit": "sqm",
            "reason": "misheard the number",
        }
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "misheard the number" in prompt
