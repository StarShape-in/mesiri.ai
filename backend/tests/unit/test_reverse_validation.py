"""ReverseTransactionCommand validation — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

from mesiri.application.finance.reverse_commands import ReverseTransactionCommand
from mesiri.application.finance.reverse_validation import validate

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
EXPENSE_ID = "55555555-5555-4555-8555-555555555555"
TRANSACTION_ID = "66666666-6666-4666-8666-666666666666"


def _command(**overrides) -> ReverseTransactionCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        target_kind="expense",
        expense_id=EXPENSE_ID,
    )
    base.update(overrides)
    return ReverseTransactionCommand(**base)


def test_valid_expense_reversal_has_no_reasons():
    assert validate(_command()) == []


def test_valid_transfer_reversal_has_no_reasons():
    reasons = validate(
        _command(target_kind="transfer", expense_id=None, money_transaction_id=TRANSACTION_ID)
    )
    assert reasons == []


def test_unknown_target_kind_is_rejected():
    reasons = validate(_command(target_kind="petty_cash"))
    assert "unknown target_kind 'petty_cash'" in reasons


def test_expense_target_without_expense_id_is_rejected():
    reasons = validate(_command(expense_id=None))
    assert "no expense to reverse" in reasons


def test_transfer_target_without_transaction_id_is_rejected():
    reasons = validate(_command(target_kind="transfer", expense_id=None))
    assert "no transfer to reverse" in reasons


def test_finance_role_is_allowed():
    assert validate(_command(created_by_role="FINANCE")) == []


def test_project_manager_role_is_rejected():
    """Unlike transfer, reversal is ADMIN/FINANCE only -- a PROJECT_MANAGER
    who may transfer money may not undo a confirmed record."""
    reasons = validate(_command(created_by_role="PROJECT_MANAGER"))
    assert "only an admin or finance user can reverse a transaction" in reasons


def test_site_engineer_role_is_rejected():
    reasons = validate(_command(created_by_role="SITE_ENGINEER"))
    assert "only an admin or finance user can reverse a transaction" in reasons


def test_missing_role_is_rejected():
    reasons = validate(_command(created_by_role=None))
    assert "only an admin or finance user can reverse a transaction" in reasons


def test_role_check_is_case_insensitive():
    assert validate(_command(created_by_role="admin")) == []
