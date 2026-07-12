"""Pure structural validation for RecordExpenseCommand — no DB, no I/O."""

from __future__ import annotations

from .commands import RecordExpenseCommand


def validate(cmd: RecordExpenseCommand) -> list[str]:
    reasons: list[str] = []
    if cmd.amount <= 0:
        reasons.append("amount must be greater than zero")
    if not cmd.currency.strip():
        reasons.append("currency is required")
    if not (cmd.category_id and cmd.category_id.strip()) and not (
        cmd.category_text and cmd.category_text.strip()
    ):
        reasons.append("category_id or category_text is required")
    if not cmd.project_id.strip():
        reasons.append("project_id is required")
    return reasons
