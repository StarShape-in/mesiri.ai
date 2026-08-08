"""domains/workforce/validation — unit tests (pure, no I/O)."""

from __future__ import annotations

from decimal import Decimal

from mesiri.domains.workforce.validation import validate
from mesiri_contracts.application.commands.labour import (
    LabourAttendanceLine,
    RecordLabourAttendanceCommand,
)

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"
TODAY = "2026-07-26"


def _cmd(lines: list[LabourAttendanceLine], *, project_id=PRJ) -> RecordLabourAttendanceCommand:
    return RecordLabourAttendanceCommand(
        command_id="cmd_1",
        idempotency_key="wf_1",
        correlation_id="cor_1",
        organization_id=ORG,
        project_id=project_id,
        site_id=None,
        lines=lines,
        occurred_date=TODAY,
        created_by=USR,
    )


def test_a_valid_mixed_attendance_passes():
    cmd = _cmd(
        [
            LabourAttendanceLine(worker_name="Ravi", trade="mason", headcount=1),
            LabourAttendanceLine(worker_name=None, trade="helper", headcount=12),
        ]
    )
    assert validate(cmd) == []


def test_unresolved_project_is_rejected():
    cmd = _cmd([LabourAttendanceLine(worker_name="Ravi")], project_id=None)
    assert "project is not resolved" in validate(cmd)


def test_zero_lines_is_rejected():
    """The canonicalization gate already catches this earlier, but the
    domain layer re-asserts its own invariant rather than trusting it."""
    cmd = _cmd([])
    assert "attendance must have at least one line" in validate(cmd)


def test_zero_headcount_line_is_rejected():
    cmd = _cmd([LabourAttendanceLine(worker_name=None, trade="helper", headcount=0)])
    reasons = validate(cmd)
    assert any("headcount must be positive" in r for r in reasons)


def test_negative_wage_is_rejected():
    cmd = _cmd(
        [LabourAttendanceLine(worker_name="Ravi", daily_wage=Decimal("-100"))]
    )
    reasons = validate(cmd)
    assert any("daily_wage cannot be negative" in r for r in reasons)


def test_a_missing_wage_is_valid():
    """P9: a wage-less line is a legitimate fast capture, not a violation."""
    cmd = _cmd([LabourAttendanceLine(worker_name="Ravi", daily_wage=None)])
    assert validate(cmd) == []


def test_a_blank_worker_name_is_rejected():
    cmd = _cmd([LabourAttendanceLine(worker_name="   ")])
    reasons = validate(cmd)
    assert any("worker_name cannot be blank" in r for r in reasons)


def test_multiple_violations_are_all_reported_with_line_numbers():
    cmd = _cmd(
        [
            LabourAttendanceLine(worker_name="Ravi", headcount=1),
            LabourAttendanceLine(worker_name=None, trade="helper", headcount=-3),
        ]
    )
    reasons = validate(cmd)
    assert any("line 2" in r for r in reasons)
    assert not any("line 1" in r for r in reasons)
