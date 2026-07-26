"""Labour command contract — the shape attendance is persisted from.

Two decisions are load-bearing and pinned here:

1. **A line is either a named person or a headcount group, and one report
   may mix both.** Real sites report both ways, often in the same message.
   Forcing a single style would push away whichever half of users doesn't
   work that way.

2. **Trade and wage are copied onto the line, not referenced.** Attendance
   is immutable history; if a line merely pointed at the register, editing
   a worker's wage next month would silently rewrite what last month's
   attendance appears to have cost.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mesiri_contracts.application.commands.labour import (
    LabourAttendanceLine,
    RecordLabourAttendanceCommand,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _command(**overrides) -> RecordLabourAttendanceCommand:
    payload = {
        "command_id": "cmd_1",
        "idempotency_key": "wf_1",
        "correlation_id": "cor_1",
        "organization_id": _uuid(),
        "project_id": _uuid(),
        "site_id": _uuid(),
        "lines": [LabourAttendanceLine(worker_name="Ravi", trade="mason")],
        "occurred_date": date(2026, 7, 26),
        "created_by": _uuid(),
    }
    payload.update(overrides)
    return RecordLabourAttendanceCommand(**payload)


# ---------------------------------------------------------------------------
# Named workers and headcount groups coexist
# ---------------------------------------------------------------------------


def test_one_attendance_can_mix_named_workers_and_headcount_groups():
    """The shape that makes the module practical on a real site::

        Ravi - Mason
        Arun - Painter
        12 Helpers
        4 Carpenters
    """
    cmd = _command(
        lines=[
            LabourAttendanceLine(worker_name="Ravi", trade="mason", daily_wage=Decimal("800")),
            LabourAttendanceLine(worker_name="Arun", trade="painter", daily_wage=Decimal("750")),
            LabourAttendanceLine(trade="helper", headcount=12, daily_wage=Decimal("600")),
            LabourAttendanceLine(trade="carpenter", headcount=4, daily_wage=Decimal("900")),
        ]
    )

    assert cmd.total_headcount == 18
    assert cmd.total_cost == Decimal("800") + Decimal("750") + Decimal("7200") + Decimal("3600")


def test_a_named_worker_defaults_to_one_person():
    line = LabourAttendanceLine(worker_name="Ravi", trade="mason")
    assert line.headcount == 1


def test_a_headcount_group_needs_no_name():
    """Reporting "12 helpers" must be a complete, valid line — this is the
    fastest possible capture and many sites work exactly this way."""
    line = LabourAttendanceLine(trade="helper", headcount=12)
    assert line.worker_name is None
    assert line.worker_id is None
    assert line.headcount == 12


# ---------------------------------------------------------------------------
# Attendance never writes the register (principle P1)
# ---------------------------------------------------------------------------


def test_an_unmatched_named_worker_carries_no_worker_id():
    """`worker_id is None` means "not in the register" — it does NOT mean
    "add them". Attendance never mutates the workforce register; promotion
    is a separate explicit act."""
    line = LabourAttendanceLine(worker_name="Someone New", trade="helper")
    assert line.worker_id is None
    assert line.worker_name == "Someone New"


# ---------------------------------------------------------------------------
# Cost is operational, not payroll
# ---------------------------------------------------------------------------


def test_line_cost_multiplies_wage_by_headcount():
    line = LabourAttendanceLine(trade="helper", headcount=10, daily_wage=Decimal("600"))
    assert line.line_cost == Decimal("6000")


def test_a_line_without_a_wage_costs_nothing_rather_than_failing():
    """Wage is optional — a supervisor recording who turned up shouldn't be
    blocked because rates weren't to hand (principle P9)."""
    line = LabourAttendanceLine(worker_name="Ravi", trade="mason")
    assert line.line_cost == Decimal("0")


def test_total_cost_of_an_attendance_with_no_wages_is_zero():
    cmd = _command(lines=[LabourAttendanceLine(trade="helper", headcount=5)])
    assert cmd.total_cost == Decimal("0")
    assert cmd.total_headcount == 5


def test_wage_is_decimal_not_float():
    """Money must never be a float. Stored per line so historical cost can't
    drift when the register is edited later."""
    line = LabourAttendanceLine(worker_name="Ravi", daily_wage=Decimal("833.33"))
    assert isinstance(line.daily_wage, Decimal)
    assert line.line_cost == Decimal("833.33")


# ---------------------------------------------------------------------------
# Scope, provenance and future-readiness (principle P8)
# ---------------------------------------------------------------------------


def test_project_id_may_be_unresolved():
    """An unresolved project is a routine outcome of context resolution. The
    mapper must never invent one — domain validation rejects it honestly."""
    cmd = _command(project_id=None)
    assert cmd.project_id is None


def test_attachment_keys_default_to_empty_not_none():
    """Recording without a photo is normal; the field should never need a
    None check at every use site."""
    assert _command().attachment_object_keys == []


def test_activity_survives_onto_the_line():
    """Carried even though V1 exposes no activity management — the
    Materials -> Activity -> Labour -> Expenses link cannot be reconstructed
    after the fact (principle P7)."""
    line = LabourAttendanceLine(worker_name="Ravi", activity="slab casting")
    assert line.activity == "slab casting"


def test_contractor_is_free_text():
    """Deliberately not an entity in V1: site vocabulary is inconsistent
    ("Kumar Team", "Local Labour"), and converting free text into an entity
    later is far easier than the reverse."""
    line = LabourAttendanceLine(trade="helper", headcount=6, contractor="Kumar Team")
    assert line.contractor == "Kumar Team"


def test_occurred_date_records_how_it_was_determined():
    assert _command().occurred_date_source == "inferred_at_confirmation"


# ---------------------------------------------------------------------------
# Contract strictness
# ---------------------------------------------------------------------------


def test_unknown_fields_are_rejected_on_the_command():
    """extra="forbid" — a typo'd field must fail loudly rather than being
    silently dropped on the way to persistence."""
    with pytest.raises(ValidationError):
        _command(unexpected_field="x")


def test_unknown_fields_are_rejected_on_a_line():
    with pytest.raises(ValidationError):
        LabourAttendanceLine(worker_name="Ravi", hours_worked=8)


def test_command_round_trips_through_json():
    """Draft actions are persisted as JSON in workflow state and replayed by
    the recovery sweep, so the command must survive a round trip intact."""
    original = _command(
        lines=[
            LabourAttendanceLine(worker_name="Ravi", trade="mason", daily_wage=Decimal("800")),
            LabourAttendanceLine(trade="helper", headcount=12, daily_wage=Decimal("600")),
        ],
        notes="half day, rain",
        attachment_object_keys=["media/att/1"],
    )
    restored = RecordLabourAttendanceCommand.model_validate_json(original.model_dump_json())

    assert restored.total_headcount == original.total_headcount
    assert restored.total_cost == original.total_cost
    assert restored.notes == "half day, rain"
    assert restored.attachment_object_keys == ["media/att/1"]
