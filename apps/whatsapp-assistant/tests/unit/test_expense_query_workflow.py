from workflows.expense_query.nodes import generate_expense_query_reply
from workflows.state import WorkflowGraphState


def test_expenses_found_reports_total_count_and_items():
    state: WorkflowGraphState = {
        "collected_fields": {
            "expense_results": {
                "total": "1200.00",
                "count": 2,
                "date_range_label": "today",
                "items": [
                    {"amount": "700.00", "description": "diesel refill", "occurred_date": "2026-07-25"},
                    {"amount": "500.00", "description": "diesel top-up", "occurred_date": "2026-07-25"},
                ],
            }
        }
    }
    result = generate_expense_query_reply(state)
    prompt = result["pending_prompt"]
    assert "today" in prompt
    assert "1200" in prompt
    assert "(2)" in prompt
    assert "diesel refill" in prompt
    assert "diesel top-up" in prompt


def test_category_filtered_query_names_the_category_in_the_reply():
    state: WorkflowGraphState = {
        "collected_fields": {
            "category_name": "diesel",
            "expense_results": {
                "total": "700.00",
                "count": 1,
                "date_range_label": "this week",
                "items": [{"amount": "700.00", "description": None, "occurred_date": "2026-07-25"}],
            },
        }
    }
    result = generate_expense_query_reply(state)
    prompt = result["pending_prompt"]
    assert "diesel" in prompt
    assert "this week" in prompt
    assert "—" in prompt  # missing description falls back to an em dash


def test_no_expenses_found_names_the_category_and_range():
    state: WorkflowGraphState = {
        "collected_fields": {
            "category_name": "diesel",
            "expense_results": {"total": "0", "count": 0, "date_range_label": "today", "items": []},
        }
    }
    result = generate_expense_query_reply(state)
    prompt = result["pending_prompt"]
    assert "No expenses" in prompt
    assert "diesel" in prompt
    assert "today" in prompt


def test_more_than_five_items_are_truncated_with_a_count():
    items = [
        {"amount": "100.00", "description": f"item {i}", "occurred_date": "2026-07-25"}
        for i in range(7)
    ]
    state: WorkflowGraphState = {
        "collected_fields": {
            "expense_results": {
                "total": "700.00",
                "count": 7,
                "date_range_label": "this month",
                "items": items,
            }
        }
    }
    result = generate_expense_query_reply(state)
    prompt = result["pending_prompt"]
    assert "item 0" in prompt
    assert "item 4" in prompt
    assert "item 5" not in prompt
    assert "and 2 more" in prompt


def test_missing_expense_results_defaults_to_zero_count():
    state: WorkflowGraphState = {"collected_fields": {}}
    result = generate_expense_query_reply(state)
    assert "No expenses" in result["pending_prompt"]


def test_missing_receipts_nudge_lists_the_unreceipted_expenses():
    state: WorkflowGraphState = {
        "collected_fields": {
            "missing_receipts": True,
            "expense_results": {
                "total": "1200.00",
                "count": 2,
                "date_range_label": "this month",
                "items": [
                    {"amount": "700.00", "description": "diesel refill", "occurred_date": "2026-07-25"},
                    {"amount": "500.00", "description": "cement bags", "occurred_date": "2026-07-20"},
                ],
            },
        }
    }
    result = generate_expense_query_reply(state)
    prompt = result["pending_prompt"]
    assert "Missing receipts" in prompt
    assert "2 expense(s)" in prompt
    assert "diesel refill" in prompt
    assert "cement bags" in prompt
    # Not the total-based phrasing the regular query uses.
    assert "Total:" not in prompt


def test_missing_receipts_nudge_with_none_found_is_a_celebratory_reply():
    state: WorkflowGraphState = {
        "collected_fields": {
            "missing_receipts": True,
            "expense_results": {"total": "0", "count": 0, "date_range_label": "this month", "items": []},
        }
    }
    result = generate_expense_query_reply(state)
    prompt = result["pending_prompt"]
    assert "No missing receipts" in prompt
    assert "this month" in prompt


def test_missing_receipts_flag_false_uses_the_regular_reply():
    """`missing_receipts` is only ever `true` or absent (see the extraction
    prompt) -- a falsy value must not accidentally trigger the nudge phrasing."""
    state: WorkflowGraphState = {
        "collected_fields": {
            "missing_receipts": False,
            "expense_results": {"total": "700.00", "count": 1, "date_range_label": "today", "items": []},
        }
    }
    result = generate_expense_query_reply(state)
    assert "Total:" in result["pending_prompt"]
