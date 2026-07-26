"""ConfirmedActionV2 -> ManageMoneyAccountCommand mapping — unit tests (pure, no I/O)."""

from __future__ import annotations

from mesiri.application.finance.mapper import build_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.MANAGE_MONEY_ACCOUNT,
        organization_id=ORG,
        user_id=USR,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def test_maps_create_fields():
    cmd = build_command(_confirmed({"action": "create", "name": "Site Cash", "account_type": "cash"}))
    assert cmd.idempotency_key == "wf_1"
    assert cmd.action == "create"
    assert cmd.name == "Site Cash"
    assert cmd.account_type == "cash"
    assert cmd.created_by == USR


def test_maps_rename_fields():
    cmd = build_command(
        _confirmed({"action": "rename", "target_name": "Site Cash", "new_name": "Kochi Cash"})
    )
    assert cmd.action == "rename"
    assert cmd.target_name == "Site Cash"
    assert cmd.new_name == "Kochi Cash"


def test_maps_deactivate_fields():
    cmd = build_command(_confirmed({"action": "deactivate", "target_name": "Site Cash"}))
    assert cmd.action == "deactivate"
    assert cmd.target_name == "Site Cash"


def test_missing_account_type_defaults_to_cash():
    cmd = build_command(_confirmed({"action": "create", "name": "Site Cash"}))
    assert cmd.account_type == "cash"


def test_maps_created_by_role():
    """Seeded by runtime/inbound_journey.py, validated in
    application/finance/validation.py -- defense-in-depth for the role gate
    that already blocks a disallowed role earlier (see
    runtime/inbound_journey.py and runtime/account_admin_journey.py)."""
    cmd = build_command(
        _confirmed({"action": "create", "name": "Site Cash", "created_by_role": "FINANCE"})
    )
    assert cmd.created_by_role == "FINANCE"


def test_missing_created_by_role_defaults_to_none():
    cmd = build_command(_confirmed({"action": "create", "name": "Site Cash"}))
    assert cmd.created_by_role is None
