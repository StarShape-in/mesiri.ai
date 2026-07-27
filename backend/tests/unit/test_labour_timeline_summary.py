"""Labour's timeline entry — the summary text and the missing-column handling.

Pure/offline tests only (no live database — see the integration suite for
that). What's worth pinning without one: the human-readable summary text, and
that labour_attendance_reports (no occurred_time column) doesn't crash the
shared projector loop that every other aggregate table also runs through.
"""

from __future__ import annotations

from mesiri.events.consumers.timeline_projector import (
    AGGREGATE_TABLES,
    EVENT_SUMMARY_BUILDERS,
    _build_summary,
    _labour_attendance_summary,
)


def test_the_summary_reads_naturally():
    assert _labour_attendance_summary({"total_headcount": 12}) == "12 workers recorded"


def test_a_single_worker_is_singular():
    assert _labour_attendance_summary({"total_headcount": 1}) == "1 worker recorded"


def test_a_missing_headcount_falls_back_rather_than_crashing():
    """A malformed payload must not block the whole batch (see
    _build_summary's own try/except, which this exercises the safe path of)."""
    assert _labour_attendance_summary({}) == "Attendance recorded"


def test_no_project_or_site_name_is_embedded_in_the_text():
    """Deliberately not "12 workers at Riverside Tower" -- matches Material's
    own summaries, which also carry no location text. timeline_entries stores
    project_id/site_id as their own columns; embedding a name here would go
    stale if the project were ever renamed."""
    summary = _labour_attendance_summary({"total_headcount": 5, "project_name": "Riverside"})
    assert "Riverside" not in summary


def test_build_summary_dispatches_the_labour_event_type():
    assert _build_summary("LabourAttendanceRecorded", {"total_headcount": 8}) == "8 workers recorded"


def test_an_unregistered_event_type_still_falls_back_safely():
    assert _build_summary("SomethingUnknown", {}) == "SomethingUnknown event"


# --- registration -----------------------------------------------------------


def test_labour_attendance_report_is_a_registered_aggregate():
    assert "labour_attendance_report" in AGGREGATE_TABLES


def test_the_labour_table_has_no_occurred_time_column():
    """The reason this table needed the projector's select to become
    conditional: attendance is a whole-day fact, not a timestamped movement,
    and a fabricated midnight time would be indistinguishable from a real
    recorded one to anyone reading timeline_entries later."""
    table = AGGREGATE_TABLES["labour_attendance_report"]
    assert "occurred_time" not in table.c
    assert "occurred_date" in table.c


def test_material_tables_still_declare_occurred_time():
    """Regression guard: the conditional column selection must not have
    quietly dropped occurred_time for the aggregates that do have it."""
    assert "occurred_time" in AGGREGATE_TABLES["material_receipt"].c
    assert "occurred_time" in AGGREGATE_TABLES["material_usage"].c


def test_labour_attendance_recorded_is_a_registered_event_type():
    assert "LabourAttendanceRecorded" in EVENT_SUMMARY_BUILDERS
