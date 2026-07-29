"""Reading a real muster roll: the P/A/H column, OT, remarks, per-line contractor.

A typed WhatsApp message says who worked. A photographed Indian muster roll
says more, and says it in shorthand -- P / A / H, a tick or a cross, an OT
column, a remarks column at the right-hand edge, and often a different
contractor per group. These cover the normalization that turns that shorthand
into the fields the command carries.

The governing rule throughout: an unreadable mark defaults to present. Being
wrong that way records a day that may not have happened, which a supervisor
sees in the confirmation and can reject. Being wrong the other way silently
deletes a real person's day of pay.
"""

from __future__ import annotations

from canonicalization.builder import _labour_line


def test_p_a_and_h_are_the_marks_the_sheet_actually_uses():
    assert _labour_line({"name": "Ravi", "attendance_status": "P"})["attendance_status"] == "present"
    assert _labour_line({"name": "Ravi", "attendance_status": "A"})["attendance_status"] == "absent"
    assert _labour_line({"name": "Ravi", "attendance_status": "H"})["attendance_status"] == "half_day"


def test_the_words_are_accepted_as_well_as_the_letters():
    for word, expected in [
        ("present", "present"),
        ("Absent", "absent"),
        ("half day", "half_day"),
        ("half_day", "half_day"),
        ("HD", "half_day"),
        ("leave", "absent"),
        ("off", "absent"),
    ]:
        line = _labour_line({"name": "Ravi", "attendance_status": word})
        assert line["attendance_status"] == expected, word


def test_a_tick_or_cross_read_as_a_boolean_still_works():
    """Vision models frequently return a tick column as true/false."""
    assert _labour_line({"name": "Ravi", "attendance_status": True})["attendance_status"] == "present"
    assert _labour_line({"name": "Ravi", "attendance_status": False})["attendance_status"] == "absent"


def test_alternative_key_names_are_accepted():
    for key in ("attendance_status", "status", "attendance", "present"):
        line = _labour_line({"name": "Ravi", key: "A"})
        assert line["attendance_status"] == "absent", key


def test_a_typed_report_carries_no_status_at_all():
    """The common case. Everyone named in a typed message worked, so the key
    is absent and the contract's default (present) applies -- rather than
    stamping "present" onto every line as noise."""
    assert "attendance_status" not in _labour_line({"name": "Ravi", "trade": "mason"})


def test_an_unreadable_mark_is_left_to_default_rather_than_guessed():
    """A smudged or unrecognised cell must not become "absent". Defaulting to
    present is the recoverable error; deleting a day's pay is not."""
    for unreadable in ("?", "~", "xx", "unknown", ""):
        assert "attendance_status" not in _labour_line(
            {"name": "Ravi", "attendance_status": unreadable}
        ), unreadable


# --- Overtime --------------------------------------------------------------

def test_overtime_is_read_from_its_own_column():
    assert _labour_line({"name": "Ravi", "overtime_hours": 2.5})["overtime_hours"] == 2.5


def test_overtime_accepts_the_names_a_sheet_uses():
    for key in ("overtime_hours", "ot_hours", "overtime"):
        assert _labour_line({"name": "Ravi", key: 3})["overtime_hours"] == 3, key


def test_no_overtime_column_means_no_overtime_key():
    assert "overtime_hours" not in _labour_line({"name": "Ravi", "trade": "mason"})


# --- Remarks and per-line contractor ---------------------------------------

def test_remarks_are_kept_verbatim():
    line = _labour_line({"name": "Ravi", "remarks": "left early — site closed 2pm"})
    assert line["remarks"] == "left early — site closed 2pm"


def test_a_line_can_carry_its_own_contractor():
    """One sheet often lists several agencies. Before this, contractor only
    existed at the top level, so a mixed sheet attributed everyone to one."""
    line = _labour_line({"name": "Ravi", "trade": "mason", "contractor": "Kumar Agency"})
    assert line["contractor"] == "Kumar Agency"


def test_a_line_can_carry_its_own_activity():
    line = _labour_line({"name": "Ravi", "activity": "column casting"})
    assert line["activity"] == "column casting"


# --- Everything still holds for a headcount group --------------------------

def test_a_headcount_group_can_be_marked_half_day():
    line = _labour_line({"trade": "helper", "headcount": 6, "attendance_status": "H"})
    assert line["worker_name"] is None
    assert line["headcount"] == 6
    assert line["attendance_status"] == "half_day"


def test_the_new_fields_never_make_an_empty_line_meaningful():
    """A row with only a remark and nothing else is not an attendance line."""
    assert _labour_line({"remarks": "site closed"}) is None
