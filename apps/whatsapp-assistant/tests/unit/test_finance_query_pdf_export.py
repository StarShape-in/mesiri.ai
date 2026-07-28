"""runtime/inbound_journey.py::_build_finance_query_pdf -- pure function,
no I/O. Pins the "send as PDF" feature: a WhatsApp user asking for their
balance/expenses "as pdf" (output_format="pdf" on the finance_query semantic
type, see platform/ai/src/mesiri_ai/adapters/{gemini,deepseek}/adapter.py)
gets a real PDF document, built from the same balance_results/expense_results
_seed_finance_query_context already seeds -- not a re-query.
"""

from __future__ import annotations

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from runtime.inbound_journey import _build_finance_query_pdf


def test_returns_none_for_a_non_finance_query_workflow():
    assert _build_finance_query_pdf(WorkflowKey.DPR_REQUEST, {}) is None


def test_builds_account_balances_pdf():
    fields = {
        "balance_results": [
            {"name": "Site Cash", "balance": "12500.00"},
            {"name": "Company Account", "balance": "450000.00"},
        ]
    }
    result = _build_finance_query_pdf(WorkflowKey.ACCOUNT_BALANCE_QUERY, fields)
    assert result is not None
    pdf_bytes, filename = result
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Account_Balances.pdf"


def test_builds_account_balances_pdf_with_no_matching_accounts():
    """No balance_results yet -- must still produce a valid PDF, not crash
    on an empty/missing list."""
    pdf_bytes, filename = _build_finance_query_pdf(WorkflowKey.ACCOUNT_BALANCE_QUERY, {})
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Account_Balances.pdf"


def test_builds_expenses_pdf():
    fields = {
        "expense_results": {
            "total": "3500.00",
            "count": 2,
            "date_range_label": "Today",
            "items": [
                {"amount": "1500.00", "description": "Diesel", "occurred_date": "2026-07-20"},
                {"amount": "2000.00", "description": None, "occurred_date": "2026-07-20"},
            ],
        }
    }
    result = _build_finance_query_pdf(WorkflowKey.EXPENSE_QUERY, fields)
    assert result is not None
    pdf_bytes, filename = result
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Expenses.pdf"


def test_builds_expenses_pdf_with_no_matching_expenses():
    pdf_bytes, filename = _build_finance_query_pdf(WorkflowKey.EXPENSE_QUERY, {})
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Expenses.pdf"
