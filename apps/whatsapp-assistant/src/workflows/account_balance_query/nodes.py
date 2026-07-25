"""Node for the account-balance-query workflow.

Reads `collected_fields['balance_results']`, seeded by the caller (a node
must never query a repository itself -- see runtime/money_account_query.py
and workflows/runtime.py's docstring) before this graph runs. Mirrors
workflows/material_inventory_query/nodes.py's shape and reasoning exactly.
"""

from __future__ import annotations

from ..state import WorkflowGraphState


def _fmt_amount(value: str) -> str:
    """Render a Decimal-as-string amount without a noisy trailing .00."""
    number = float(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}"


def generate_balance_reply(state: WorkflowGraphState) -> dict:
    """No draft_action -- this is read-only, so WorkflowRuntime completes it
    without a confirmation."""
    fields = state.get("collected_fields", {})
    account_name = fields.get("account_name")
    accounts: list[dict] = fields.get("balance_results") or []

    if not accounts:
        if account_name:
            return {"pending_prompt": f"I couldn't find an account named '{account_name}'."}
        return {"pending_prompt": "There are no accounts set up yet."}

    if len(accounts) == 1:
        account = accounts[0]
        return {
            "pending_prompt": f"💰 {account['name']}: ₹{_fmt_amount(account['balance'])}"
        }

    lines = ["💰 *Account balances*", ""]
    total = 0.0
    for account in accounts:
        lines.append(f"{account['name']} — ₹{_fmt_amount(account['balance'])}")
        total += float(account["balance"])
    lines.append("")
    lines.append(f"Total: ₹{_fmt_amount(str(total))}")
    return {"pending_prompt": "\n".join(lines)}
