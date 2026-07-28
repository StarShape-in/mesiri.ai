"""runtime/inbound_journey.py::_build_query_pdf -- pure function, no I/O.

Pins the "send as PDF" feature across all five query workflows it covers: a
WhatsApp user asking for a query's answer "as pdf" (output_format="pdf" on
finance_query/inventory_query/labour_query/activity_query, see
platform/ai/src/mesiri_ai/adapters/{gemini,deepseek}/adapter.py) gets a real
PDF document, built from whichever *_results/*_levels key the matching
_seed_* function already seeded -- never a re-query.
"""

from __future__ import annotations

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from runtime.inbound_journey import _build_query_pdf


def test_returns_none_for_a_non_query_workflow():
    assert _build_query_pdf(WorkflowKey.DPR_REQUEST, {}) is None


def test_builds_account_balances_pdf():
    fields = {
        "balance_results": [
            {"name": "Site Cash", "balance": "12500.00"},
            {"name": "Company Account", "balance": "450000.00"},
        ]
    }
    result = _build_query_pdf(WorkflowKey.ACCOUNT_BALANCE_QUERY, fields)
    assert result is not None
    pdf_bytes, filename = result
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Account_Balances.pdf"


def test_builds_account_balances_pdf_with_no_matching_accounts():
    """No balance_results yet -- must still produce a valid PDF, not crash
    on an empty/missing list."""
    pdf_bytes, filename = _build_query_pdf(WorkflowKey.ACCOUNT_BALANCE_QUERY, {})
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
    result = _build_query_pdf(WorkflowKey.EXPENSE_QUERY, fields)
    assert result is not None
    pdf_bytes, filename = result
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Expenses.pdf"


def test_builds_expenses_pdf_with_no_matching_expenses():
    pdf_bytes, filename = _build_query_pdf(WorkflowKey.EXPENSE_QUERY, {})
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Expenses.pdf"


def test_builds_material_inventory_pdf():
    fields = {
        "inventory_levels": [
            {
                "material_name": "Cement",
                "unit": "bags",
                "received": 500.0,
                "used": 320.0,
                "current_stock": 180.0,
            },
            {
                "material_name": "Steel",
                "unit": "kg",
                "received": 2000.0,
                "used": 1500.0,
                "current_stock": 500.0,
            },
        ]
    }
    result = _build_query_pdf(WorkflowKey.MATERIAL_INVENTORY_QUERY, fields)
    assert result is not None
    pdf_bytes, filename = result
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Material_Inventory.pdf"


def test_builds_material_inventory_pdf_with_no_recorded_stock():
    pdf_bytes, filename = _build_query_pdf(WorkflowKey.MATERIAL_INVENTORY_QUERY, {})
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Material_Inventory.pdf"


def test_builds_activity_log_pdf():
    fields = {
        "activity_search_results": {
            "activities": [
                {
                    "work_type": "Plastering",
                    "narrative": "2nd floor east wing",
                    "status": "COMPLETED",
                    "activity_date": "2026-07-20",
                }
            ],
            "activity_count": 1,
            "open_issues": [
                {"issue_type": "MATERIAL_SHORTAGE", "severity": "HIGH", "narrative": "No cement"}
            ],
            "open_issue_count": 1,
            "date_range_label": "Today",
        }
    }
    result = _build_query_pdf(WorkflowKey.ACTIVITY_QUERY, fields)
    assert result is not None
    pdf_bytes, filename = result
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Site_Activity_Log.pdf"


def test_builds_activity_log_pdf_with_no_activities_logged():
    pdf_bytes, filename = _build_query_pdf(WorkflowKey.ACTIVITY_QUERY, {})
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Site_Activity_Log.pdf"


def test_builds_labour_attendance_pdf():
    fields = {
        "labour_results": {
            "headcount": 15,
            "total_cost": "9200",
            "date_range_label": "Today",
            "rows": [
                {
                    "occurred_date": "2026-07-20",
                    "worker_name": "Ravi",
                    "trade": "mason",
                    "headcount": 1,
                    "daily_wage": "800",
                },
                {
                    "occurred_date": "2026-07-20",
                    "worker_name": None,
                    "trade": "helper",
                    "headcount": 12,
                    "daily_wage": "600",
                },
            ],
        }
    }
    result = _build_query_pdf(WorkflowKey.LABOUR_QUERY, fields)
    assert result is not None
    pdf_bytes, filename = result
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Labour_Attendance.pdf"


def test_builds_labour_attendance_pdf_with_no_recorded_attendance():
    pdf_bytes, filename = _build_query_pdf(WorkflowKey.LABOUR_QUERY, {})
    assert pdf_bytes.startswith(b"%PDF")
    assert filename == "Labour_Attendance.pdf"
