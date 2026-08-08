"""Pure structural validation for RecordExpenseCommand — no DB, no I/O.

category_id/category_text presence is deliberately not checked here:
category is documented as optional on the extraction side (see
mesiri_contracts.assistant.candidates.ExpenseCandidate), and neither entry
point needs a structural guard for it — REST's RecordExpenseRequest already
requires category_id via its Pydantic schema, and the WhatsApp/CQRS path's
resolver (resolution.py) falls back to a default "Uncategorized" category
when neither is given, rather than rejecting.
"""

from __future__ import annotations

from .commands import RecordExpenseCommand


def validate(cmd: RecordExpenseCommand) -> list[str]:
    reasons: list[str] = []
    if cmd.amount <= 0:
        reasons.append("amount must be greater than zero")
    if not cmd.currency.strip():
        reasons.append("currency is required")
    if not cmd.project_id.strip():
        reasons.append("project_id is required")
    if cmd.account_id is not None and cmd.paid_from_own_pocket:
        reasons.append("cannot select an account and 'paid from own pocket' at the same time")
    return reasons
