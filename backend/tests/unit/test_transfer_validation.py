"""TransferMoneyCommand validation — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from mesiri.application.finance.transfer_commands import TransferMoneyCommand
from mesiri.application.finance.transfer_validation import validate

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
ACC_A = "55555555-5555-4555-8555-555555555555"
ACC_B = "66666666-6666-4666-8666-666666666666"


def _command(**overrides) -> TransferMoneyCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        from_account_id=ACC_A,
        to_account_id=ACC_B,
        amount=Decimal("500.00"),
        occurred_date=date.today(),
    )
    base.update(overrides)
    return TransferMoneyCommand(**base)


def test_valid_transfer_has_no_reasons():
    assert validate(_command()) == []


def test_non_positive_amount_is_rejected():
    assert "amount must be greater than zero" in validate(_command(amount=Decimal("0")))
    assert "amount must be greater than zero" in validate(_command(amount=Decimal("-5")))


def test_missing_accounts_are_rejected():
    reasons = validate(_command(from_account_id="", to_account_id=""))
    assert "both accounts are required" in reasons


def test_same_account_both_sides_is_rejected():
    reasons = validate(_command(from_account_id=ACC_A, to_account_id=ACC_A))
    assert "cannot transfer to the same account" in reasons


def test_finance_role_is_allowed():
    assert validate(_command(created_by_role="FINANCE")) == []


def test_project_manager_role_is_allowed():
    assert validate(_command(created_by_role="PROJECT_MANAGER")) == []


def test_site_engineer_role_is_rejected():
    reasons = validate(_command(created_by_role="SITE_ENGINEER"))
    assert "only an admin, finance user, or project manager can transfer money" in reasons


def test_missing_role_is_rejected():
    reasons = validate(_command(created_by_role=None))
    assert "only an admin, finance user, or project manager can transfer money" in reasons


def test_role_check_is_case_insensitive():
    assert validate(_command(created_by_role="admin")) == []
