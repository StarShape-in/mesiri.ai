"""Progress domain validation (Daily Reporting) — pure functions, no I/O, no SQL.

Mirrors domains/workforce/validation.py and domains/materials/validation.py:
runs in the Application Handler *before* any transaction opens, returning
violation reasons rather than raising, so the Handler can choose between
persist_success and persist_rejection without exception handling around
business rules.

This validates command *shape*, not resolution — unit-text resolution and
Activity-existence checks happen in application/progress/resolution.py,
which needs a connection and therefore runs inside the transaction.
"""

from __future__ import annotations

from mesiri_contracts.application.commands.progress import (
    AddProgressUpdateCommand,
    CreateActivityCommand,
)

_VALID_UPDATE_KINDS = frozenset(
    {"STARTED", "PROGRESS", "PAUSED", "RESUMED", "COMPLETED", "NOTE"}
)


def validate_create_activity(cmd: CreateActivityCommand) -> list[str]:
    """Return violation reasons; empty list means valid."""
    reasons: list[str] = []
    if cmd.project_id is None:
        reasons.append("project is not resolved")
    if cmd.site_id is None:
        reasons.append("site is not resolved")

    # P10: a narrative-only report (zero quantities) is valid — do not
    # require quantities here. Do require that whatever quantities ARE
    # present are well-formed.
    for index, q in enumerate(cmd.quantities):
        prefix = f"quantity {index + 1}"
        if q.quantity <= 0:
            reasons.append(f"{prefix}: quantity must be positive")
        if not q.unit.strip():
            reasons.append(f"{prefix}: unit is required when a quantity is given")

    if not cmd.narrative and not cmd.quantities:
        # Not literally impossible (e.g. evidence-only), but a header with
        # nothing to say and nothing measured is not a useful Activity record.
        reasons.append("activity must have a narrative or at least one quantity")

    return reasons


def validate_add_progress_update(cmd: AddProgressUpdateCommand) -> list[str]:
    """Return violation reasons; empty list means valid."""
    reasons: list[str] = []
    if cmd.update_kind not in _VALID_UPDATE_KINDS:
        reasons.append(f"unrecognized update_kind: {cmd.update_kind}")

    if cmd.quantity is not None:
        if cmd.quantity <= 0:
            reasons.append("quantity must be positive")
        if not cmd.unit or not cmd.unit.strip():
            reasons.append("unit is required when a quantity is given")

    if not cmd.narrative and cmd.quantity is None and cmd.update_kind == "NOTE":
        reasons.append("a NOTE update needs a narrative or a quantity")

    return reasons
