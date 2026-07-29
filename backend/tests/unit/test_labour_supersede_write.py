"""The INSERT must actually write `corrects_report_id`.

Migration 0371 reserved the column, `_superseded_report_ids()` reads it, and
every total already excludes a report that another report corrects. But the
INSERT in labour_execution.py omitted the column entirely, so it was always
NULL and the guard could never fire -- which is why production carries 14
separate reports for a single site-day, all counting toward the same totals.

The gap was invisible because both halves looked correct in isolation. This
pins the column into the statement itself, so removing it from the INSERT
fails here rather than silently reverting to double-counting.
"""

from __future__ import annotations

import inspect

from mesiri.infrastructure.postgres.repositories import labour_execution


def _persist_success_source() -> str:
    return inspect.getsource(labour_execution.PostgresLabourExecutionRepository.persist_success)


def test_the_report_insert_names_the_corrects_report_id_column():
    """Asserts against the SQL column list specifically.

    An earlier version of this test searched a loose slice of the method and
    passed even with the column removed from the INSERT, because the params
    dict below it still mentioned the name -- proving the wrong thing while
    looking green. Both halves of the statement are pinned separately here.
    """
    source = _persist_success_source()
    assert "corrects_report_id, created_by)" in source, (
        "the supersede column was dropped from the INSERT's column list -- a "
        "re-sent report will silently double the day's totals again"
    )


def test_the_insert_binds_a_placeholder_for_it():
    """A column in the list with no matching placeholder would not even
    execute; pinning both means neither half can drift alone."""
    source = _persist_success_source()
    assert ":corrects_report_id, :created_by)" in source


def test_the_value_comes_from_the_command_not_a_literal():
    """Hardcoding NULL here would keep the column present but just as dead."""
    source = _persist_success_source()
    assert "cmd.corrects_report_id" in source


def test_it_is_passed_through_the_optional_uuid_helper():
    """The command carries a string; the column is a UUID foreign key. Every
    other nullable id in this method goes through the same helper."""
    source = _persist_success_source()
    assert "_optional_uuid(cmd.corrects_report_id)" in source


def test_the_command_accepts_a_correction_target():
    from mesiri_contracts.application.commands.labour import RecordLabourAttendanceCommand

    fields = RecordLabourAttendanceCommand.model_fields
    assert "corrects_report_id" in fields
    # Optional, because most reports correct nothing -- a required field here
    # would force every caller to invent a value.
    assert fields["corrects_report_id"].default is None
