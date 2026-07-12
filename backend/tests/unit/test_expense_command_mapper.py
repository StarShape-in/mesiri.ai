"""ConfirmedActionV2 -> RecordExpenseCommand mapping — unit tests (pure, no I/O)."""

from __future__ import annotations

from decimal import Decimal

from mesiri.application.expenses.mapper import build_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"
USR = "22222222-2222-4222-8222-222222222222"


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.RECORD_EXPENSE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def test_maps_fields_into_command():
    confirmed = _confirmed({"amount": 250, "category": "materials", "description": "cement bags"})
    cmd = build_command(confirmed)

    assert cmd.idempotency_key == "wf_1"
    assert cmd.organization_id == ORG
    assert cmd.project_id == PRJ
    assert cmd.site_id == SITE
    assert cmd.amount == Decimal("250")
    assert cmd.category_id is None
    assert cmd.category_text == "materials"
    assert cmd.description == "cement bags"
    assert cmd.source == "whatsapp"
    assert cmd.correlation_id == "cor_1"
    assert cmd.created_by == USR


def test_missing_category_maps_to_none_text():
    confirmed = _confirmed({"amount": 100})
    cmd = build_command(confirmed)
    assert cmd.category_text is None


def test_non_numeric_amount_defaults_to_zero_for_validation_to_catch():
    confirmed = _confirmed({"amount": "not a number", "category": "fuel"})
    cmd = build_command(confirmed)
    assert cmd.amount == Decimal("0")
