"""Pure structural validation for ManageMoneyAccountCommand — no DB, no I/O.

Duplicate-name (create) / account-not-found (rename, deactivate) checks are
deliberately not here — those need a DB round trip and belong to
resolution.py's PostgresAccountLookupResolver, mirroring
application/expenses/validation.py's split between structural and
DB-backed checks.
"""

from __future__ import annotations

from .commands import ManageMoneyAccountCommand

_VALID_ACTIONS = {"create", "rename", "deactivate"}
_VALID_ACCOUNT_TYPES = {"cash", "bank", "employee_advance", "other"}


def validate(cmd: ManageMoneyAccountCommand) -> list[str]:
    reasons: list[str] = []
    if cmd.action not in _VALID_ACTIONS:
        reasons.append(f"unknown action '{cmd.action}'")
        return reasons

    if cmd.action == "create":
        if not (cmd.name or "").strip():
            reasons.append("account name is required")
        if cmd.account_type not in _VALID_ACCOUNT_TYPES:
            reasons.append(f"unknown account type '{cmd.account_type}'")
    elif cmd.action == "rename":
        if not (cmd.target_name or "").strip():
            reasons.append("the account to rename is required")
        if not (cmd.new_name or "").strip():
            reasons.append("the new name is required")
    else:  # deactivate
        if not (cmd.target_name or "").strip():
            reasons.append("the account to deactivate is required")

    return reasons
