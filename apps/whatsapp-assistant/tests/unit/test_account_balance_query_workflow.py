from workflows.account_balance_query.nodes import generate_balance_reply
from workflows.state import WorkflowGraphState


def test_single_account_reports_its_balance():
    state: WorkflowGraphState = {
        "collected_fields": {
            "account_name": "Site Cash",
            "balance_results": [{"name": "Site Cash", "balance": "3800.00"}],
        }
    }
    result = generate_balance_reply(state)
    prompt = result["pending_prompt"]
    assert "Site Cash" in prompt
    assert "3800" in prompt


def test_multiple_accounts_lists_each_and_a_total():
    state: WorkflowGraphState = {
        "collected_fields": {
            "balance_results": [
                {"name": "Site Cash", "balance": "3800.00"},
                {"name": "Company Bank", "balance": "100000.00"},
            ]
        }
    }
    result = generate_balance_reply(state)
    prompt = result["pending_prompt"]
    assert "Site Cash" in prompt
    assert "Company Bank" in prompt
    assert "3800" in prompt
    assert "100000" in prompt
    assert "Total: ₹103800" in prompt


def test_no_match_for_named_account():
    state: WorkflowGraphState = {
        "collected_fields": {"account_name": "Nonexistent", "balance_results": []}
    }
    result = generate_balance_reply(state)
    assert "Nonexistent" in result["pending_prompt"]
    assert "couldn't find" in result["pending_prompt"]


def test_no_accounts_at_all():
    state: WorkflowGraphState = {"collected_fields": {"balance_results": []}}
    result = generate_balance_reply(state)
    assert "no accounts" in result["pending_prompt"].lower()


def test_fractional_balance_formats_without_trailing_zeros():
    state: WorkflowGraphState = {
        "collected_fields": {
            "account_name": "Site Cash",
            "balance_results": [{"name": "Site Cash", "balance": "1250.50"}],
        }
    }
    result = generate_balance_reply(state)
    assert "1250.50" in result["pending_prompt"]
