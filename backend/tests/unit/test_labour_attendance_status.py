"""A muster roll's P / A / H column, and what it costs to ignore it.

Every attendance line recorded before migration 0456 was assumed present,
which is correct for a typed message: a supervisor listing names is listing
who worked. A photographed muster roll is different -- it lists the whole
crew, absentees included -- so reading one sheet without this would invent a
day's work, and a day's wage, for everyone who did not turn up.

Half days are expressed here rather than by making `headcount` fractional:
headcount is a count of people, and 0.5 people is not a thing. The day
fraction is applied when totalling.
"""

from __future__ import annotations

from decimal import Decimal

from mesiri.infrastructure.postgres.repositories.workforce import _line_totals
from mesiri_contracts.application.commands.labour import (
    LabourAttendanceLine,
    RecordLabourAttendanceCommand,
)

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"


def _line(**kw) -> LabourAttendanceLine:
    defaults = dict(worker_name="Ravi", trade="mason", headcount=1, daily_wage=Decimal("800"))
    defaults.update(kw)
    return LabourAttendanceLine(**defaults)


def _cmd(lines) -> RecordLabourAttendanceCommand:
    return RecordLabourAttendanceCommand(
        command_id="cmd_1",
        idempotency_key="idem_1",
        correlation_id="cor_1",
        organization_id=ORG,
        project_id=PRJ,
        site_id=None,
        lines=lines,
        occurred_date=__import__("datetime").date(2026, 7, 29),
        created_by=USR,
    )


# --- The contract ----------------------------------------------------------

def test_a_line_is_present_unless_the_sheet_says_otherwise():
    """The default has to be present: it is what every typed report means and
    what every row written before this existed meant."""
    assert _line().attendance_status == "present"
    assert _line().day_fraction == Decimal("1")


def test_an_absent_line_contributes_no_cost():
    """Charging a full day against a row marked A would invent money for
    someone the sheet says was not there."""
    assert _line(attendance_status="absent").line_cost == Decimal("0")


def test_a_half_day_costs_half():
    assert _line(attendance_status="half_day").line_cost == Decimal("400")


def test_a_half_day_group_costs_half_for_everyone_on_the_line():
    line = _line(worker_name=None, headcount=6, attendance_status="half_day")
    assert line.line_cost == Decimal("2400")


def test_absent_workers_are_not_counted_in_the_confirmed_headcount():
    """A sheet of 20 with 3 absent is 17 workers, and 17 is the number the
    supervisor is asked to confirm."""
    cmd = _cmd([
        _line(worker_name="A"),
        _line(worker_name="B"),
        _line(worker_name="C", attendance_status="absent"),
    ])
    assert cmd.total_headcount == 2
    assert cmd.total_cost == Decimal("1600")


def test_a_half_day_still_counts_as_a_person_present():
    """They were on site. Their *cost* is halved, not their existence."""
    cmd = _cmd([_line(worker_name="A", attendance_status="half_day")])
    assert cmd.total_headcount == 1
    assert cmd.total_cost == Decimal("400")


def test_an_absent_line_is_still_recorded():
    """"Nobody reported Ravi" and "Ravi was marked absent" are different
    facts, and the second one is worth keeping."""
    cmd = _cmd([_line(worker_name="Ravi", attendance_status="absent")])
    assert len(cmd.lines) == 1
    assert cmd.lines[0].worker_name == "Ravi"


# --- The dashboard's own totals, which must agree ---------------------------

def test_line_totals_skips_absent_and_halves_half_days():
    """_line_totals feeds the Attendance page; the command feeds the WhatsApp
    confirmation. They have disagreed about the same report once before."""
    headcount, cost = _line_totals([
        {"headcount": 1, "daily_wage": Decimal("800"), "attendance_status": "present"},
        {"headcount": 1, "daily_wage": Decimal("800"), "attendance_status": "absent"},
        {"headcount": 2, "daily_wage": Decimal("800"), "attendance_status": "half_day"},
    ])
    assert headcount == 3
    assert cost == Decimal("1600.00")


def test_a_line_with_no_status_is_treated_as_present():
    """Every row written before migration 0456 has NULL here."""
    headcount, cost = _line_totals([{"headcount": 1, "daily_wage": Decimal("800")}])
    assert headcount == 1
    assert cost == Decimal("800.00")


def test_the_two_totals_agree_on_the_same_lines():
    lines = [
        _line(worker_name="A"),
        _line(worker_name="B", attendance_status="half_day"),
        _line(worker_name="C", attendance_status="absent"),
    ]
    cmd = _cmd(lines)
    headcount, cost = _line_totals([
        {
            "headcount": line.headcount,
            "daily_wage": line.daily_wage,
            "attendance_status": line.attendance_status,
        }
        for line in lines
    ])
    assert headcount == cmd.total_headcount
    assert cost == cmd.total_cost.quantize(Decimal("0.01"))


# --- Overtime and remarks are captured, not interpreted ---------------------

def test_overtime_is_captured_without_being_paid():
    """OT rates differ per contractor and are not being guessed at, so the
    hours are stored and the cost is unaffected."""
    line = _line(overtime_hours=Decimal("2.5"))
    assert line.overtime_hours == Decimal("2.5")
    assert line.line_cost == Decimal("800")


def test_remarks_ride_along_untouched():
    assert _line(remarks="left early, site closed 2pm").remarks == "left early, site closed 2pm"


def test_both_are_optional():
    line = _line()
    assert line.overtime_hours is None
    assert line.remarks is None
