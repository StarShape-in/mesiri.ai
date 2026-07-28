"""Finance's timeline entries — the summary text and the aggregate registration.

Pure/offline tests only (no live database — see the integration suite for
that). Pins the fix for the "finance" timeline category being permanently
unreachable: neither `expense` nor `money_transaction` was registered in
AGGREGATE_TABLES and neither write path ever wrote outbox_events, so no
Expense*/MoneyTransaction* event type could ever appear in timeline_entries.
"""

from __future__ import annotations

from mesiri.events.consumers.timeline_projector import (
    AGGREGATE_TABLES,
    EVENT_SUMMARY_BUILDERS,
    _build_summary,
)


def test_expense_is_a_registered_aggregate():
    assert "expense" in AGGREGATE_TABLES


def test_expense_table_exposes_project_and_site_id():
    table = AGGREGATE_TABLES["expense"]
    assert "project_id" in table.c
    assert "site_id" in table.c
    assert "occurred_date" in table.c
    assert "occurred_time" in table.c


def test_money_transaction_is_a_registered_aggregate():
    assert "money_transaction" in AGGREGATE_TABLES


def test_money_transaction_table_has_no_project_or_site_scope():
    """Unlike every other aggregate, a transfer between two money_accounts
    has no single project/site to attribute it to — the projector's batch
    loop must tolerate this rather than assuming every aggregate carries
    project_id/site_id."""
    table = AGGREGATE_TABLES["money_transaction"]
    assert "project_id" not in table.c
    assert "site_id" not in table.c
    assert "organization_id" in table.c


def test_expense_recorded_summary_names_amount_and_category():
    summary = _build_summary(
        "ExpenseRecorded", {"amount": "1500.00", "currency": "INR", "category_text": "Cement"}
    )
    assert summary == "INR 1500.00 expense recorded (Cement)"


def test_expense_recorded_summary_falls_back_without_category():
    summary = _build_summary("ExpenseRecorded", {"amount": "500", "currency": "INR"})
    assert summary == "INR 500 expense recorded"


def test_expense_voided_summary():
    assert _build_summary("ExpenseVoided", {}) == "Expense voided"


def test_money_transaction_transferred_summary():
    summary = _build_summary("MoneyTransactionTransferred", {"amount": "2000", "currency": "INR"})
    assert summary == "INR 2000 transferred between accounts"


def test_money_transaction_reversed_summary():
    assert _build_summary("MoneyTransferReversed", {}) == "Money transfer reversed"


def test_all_four_finance_event_types_are_registered():
    assert "ExpenseRecorded" in EVENT_SUMMARY_BUILDERS
    assert "ExpenseVoided" in EVENT_SUMMARY_BUILDERS
    assert "MoneyTransactionTransferred" in EVENT_SUMMARY_BUILDERS
    assert "MoneyTransferReversed" in EVENT_SUMMARY_BUILDERS
