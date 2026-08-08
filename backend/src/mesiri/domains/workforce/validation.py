"""Labour attendance domain validation (M8) — pure functions, no I/O, no SQL.

Mirrors domains/materials/validation.py: runs in the Application Handler
*before* any transaction opens (validation needs no connection at all), and
returns violation reasons rather than raising, so the Handler can decide
between persist_success and persist_rejection without a try/except around
business rules.

Worker matching itself (is this "Ravi" the one in the register?) already
happened in the workflow before confirmation (workflows/labour_update/nodes.py's
match_workers) — this validates the command's *shape*, not who anyone is.
"""

from __future__ import annotations

from mesiri_contracts.application.commands.labour import RecordLabourAttendanceCommand


def validate(cmd: RecordLabourAttendanceCommand) -> list[str]:
    """Return violation reasons; empty list means valid."""
    reasons: list[str] = []
    if cmd.project_id is None:
        reasons.append("project is not resolved")
    if not cmd.lines:
        # An attendance naming and counting nobody is caught earlier, at
        # canonicalization (REQUIRED_FIELDS requires `lines`), but the
        # domain layer re-checks its own invariant rather than trusting an
        # upstream gate stayed correct.
        reasons.append("attendance must have at least one line")

    for index, line in enumerate(cmd.lines):
        prefix = f"line {index + 1}"
        if line.headcount <= 0:
            reasons.append(f"{prefix}: headcount must be positive")
        if line.daily_wage is not None and line.daily_wage < 0:
            reasons.append(f"{prefix}: daily_wage cannot be negative")
        if line.worker_name is not None and not line.worker_name.strip():
            # A named line with an empty/whitespace name is neither a person
            # nor a valid headcount group -- reject rather than silently
            # treating it as one or the other.
            reasons.append(f"{prefix}: worker_name cannot be blank")
        if line.worker_name is None and line.headcount < 1:
            reasons.append(f"{prefix}: a headcount group needs at least 1 person")

    return reasons
