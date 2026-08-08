"""Material workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.material.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


def _base_state(workflow_key: WorkflowKey, fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": workflow_key.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": PRJ,
        "site_id": SITE,
        "collected_fields": fields,
    }


def test_build_draft_material_receipt():
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT,
        {"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.action_type is DraftActionType.RECORD_MATERIAL_RECEIPT
    assert draft.fields == {"material_name": "cement", "quantity": 20, "unit": "bags"}
    assert draft.workflow_instance_id == "wf_1"
    assert draft.correlation_id == "cor_1"
    assert draft.organization_id == ORG
    assert draft.project_id == PRJ
    assert draft.site_id == SITE


def test_build_draft_material_usage():
    state = _base_state(
        WorkflowKey.MATERIAL_USAGE,
        {"material_name": "sand", "quantity": 5, "unit": "tons"},
    )
    update = build_draft(state)
    assert update["draft_action"].action_type is DraftActionType.RECORD_MATERIAL_USAGE


def test_build_draft_missing_collected_fields_defaults_empty():
    state = _base_state(WorkflowKey.MATERIAL_RECEIPT, {})
    del state["collected_fields"]
    update = build_draft(state)
    assert update["draft_action"].fields == {}


@pytest.mark.parametrize(
    "unsupported_key", [WorkflowKey.EXPENSE_SUBMIT, WorkflowKey.EQUIPMENT_USAGE]
)
def test_build_draft_unsupported_workflow_key_raises(unsupported_key: WorkflowKey) -> None:
    state = _base_state(unsupported_key, {})
    with pytest.raises(KeyError):
        build_draft(state)


def test_request_confirmation_sets_prompt_from_draft():
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT,
        {"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    state.update(build_draft(state))
    update = request_confirmation(state)
    prompt = update["pending_prompt"]
    assert "Material Receipt" in prompt
    assert "cement" in prompt
    assert "20" in prompt
    assert "YES" in prompt


def test_available_stock_never_shown_as_a_draft_field():
    state = _base_state(
        WorkflowKey.MATERIAL_USAGE,
        {"material_name": "cement", "quantity": 40, "unit": "bags", "available_stock": 46.0},
    )
    update = build_draft(state)
    assert "available_stock" not in update["draft_action"].fields


def test_confirmation_warns_when_usage_exceeds_available_stock():
    state = _base_state(
        WorkflowKey.MATERIAL_USAGE,
        {"material_name": "cement", "quantity": 100, "unit": "bags", "available_stock": 46.0},
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Only 46 bags in stock" in prompt
    assert "100" in prompt


def test_confirmation_has_no_warning_when_stock_is_sufficient():
    state = _base_state(
        WorkflowKey.MATERIAL_USAGE,
        {"material_name": "cement", "quantity": 20, "unit": "bags", "available_stock": 46.0},
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "in stock" not in prompt


def test_receipt_never_gets_a_low_stock_warning():
    """The warning is meaningless for an inflow -- only usage can exceed stock."""
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT,
        {"material_name": "cement", "quantity": 500, "unit": "bags", "available_stock": 46.0},
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "in stock" not in prompt


# --- date display (STA-166 backport) ---------------------------------------


def test_confirmation_shows_a_stated_date_without_the_assumed_marker():
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT,
        {
            "material_name": "cement",
            "quantity": 20,
            "unit": "bags",
            "occurred_date": "2026-07-20",
            "occurred_date_source": "stated_by_user",
        },
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Date: 20 Jul 2026" in prompt
    assert "assumed" not in prompt


def test_confirmation_admits_when_the_date_was_guessed():
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT,
        {
            "material_name": "cement",
            "quantity": 20,
            "unit": "bags",
            "occurred_date": "2026-07-27",
            "occurred_date_source": "inferred_at_confirmation",
        },
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Date: 27 Jul 2026 (assumed today)" in prompt


def test_confirmation_never_shows_the_raw_date_plumbing():
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT,
        {
            "material_name": "cement",
            "quantity": 20,
            "unit": "bags",
            "occurred_date": "2026-07-27",
            "occurred_date_source": "inferred_at_confirmation",
        },
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "occurred_date_source" not in prompt
    assert "inferred_at_confirmation" not in prompt


def test_confirmation_omits_the_date_line_when_there_is_no_date():
    """An older draft persisted before dating shipped must still render."""
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT, {"material_name": "cement", "quantity": 20, "unit": "bags"}
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Date:" not in prompt
