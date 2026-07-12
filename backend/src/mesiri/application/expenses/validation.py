"""Pure structural validation for RecordExpenseCommand — no DB, no I/O."""

from __future__ import annotations

from .commands import RecordExpenseCommand


def validate(cmd: RecordExpenseCommand) -> list[str]:
    reasons: list[str] = []
    if cmd.amount <= 0:
        reasons.append("amount must be greater than zero")
    if not cmd.currency.strip():
        reasons.append("currency is required")
    if not cmd.category_id.strip():
        reasons.append("category_id is required")
    if not cmd.project_id.strip():
        reasons.append("project_id is required")
    return reasons
