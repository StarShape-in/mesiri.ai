"""ManageMoneyAccountCommand validation — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

from mesiri.application.finance.commands import ManageMoneyAccountCommand
from mesiri.application.finance.validation import validate

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _command(**overrides) -> ManageMoneyAccountCommand:
    base = dict(idempotency_key="idem_1", organization_id=ORG, created_by=USR, action="create")
    base.update(overrides)
    return ManageMoneyAccountCommand(**base)


def test_create_with_name_has_no_reasons():
    assert validate(_command(name="Site Cash")) == []


def test_create_without_name_is_rejected():
    assert "account name is required" in validate(_command(name=None))
    assert "account name is required" in validate(_command(name="   "))


def test_create_with_unknown_account_type_is_rejected():
    assert "unknown account type 'crypto'" in validate(
        _command(name="Site Cash", account_type="crypto")
    )


def test_rename_requires_target_and_new_name():
    reasons = validate(_command(action="rename", target_name=None, new_name=None))
    assert "the account to rename is required" in reasons
    assert "the new name is required" in reasons


def test_rename_with_both_names_has_no_reasons():
    assert validate(_command(action="rename", target_name="Site Cash", new_name="Kochi Cash")) == []


def test_deactivate_requires_target():
    assert "the account to deactivate is required" in validate(
        _command(action="deactivate", target_name=None)
    )


def test_deactivate_with_target_has_no_reasons():
    assert validate(_command(action="deactivate", target_name="Site Cash")) == []


def test_unknown_action_is_rejected():
    reasons = validate(_command(action="delete", target_name="Site Cash"))
    assert "unknown action 'delete'" in reasons
