"""Activity's timeline entry — the summary text and the column-aliasing fix.

Pure/offline tests only (no live database — see the integration suite for
that). Pins the fix for a real bug: activities uses activity_date/started_at
(not occurred_date/occurred_time), so until AGGREGATE_TABLES registered an
alias, every ActivityCreated/ActivityProgressUpdateAdded/
ActivityEvidenceAttached outbox row hit the "source row not found" orphan
path and was marked published without ever reaching timeline_entries.
"""

from __future__ import annotations

from mesiri.events.consumers.timeline_projector import (
    AGGREGATE_TABLES,
    EVENT_SUMMARY_BUILDERS,
    _build_summary,
)


def test_activity_is_a_registered_aggregate():
    assert "activity" in AGGREGATE_TABLES


def test_activity_table_exposes_occurred_date_and_time_under_the_shared_names():
    """The whole point of the key= aliasing -- the projector's batch loop
    reads source_table.c.occurred_date/occurred_time uniformly across every
    aggregate, so activities' own activity_date/started_at column names
    must not leak through as a special case the loop has to know about."""
    table = AGGREGATE_TABLES["activity"]
    assert "occurred_date" in table.c
    assert "occurred_time" in table.c
    # The Python-side key is aliased; the underlying DB column name is not.
    assert table.c.occurred_date.name == "activity_date"
    assert table.c.occurred_time.name == "started_at"


def test_activity_created_summary_names_the_work_type():
    summary = _build_summary("ActivityCreated", {"work_type": "Plastering"})
    assert summary == "Plastering activity started"


def test_activity_created_summary_falls_back_without_a_work_type():
    summary = _build_summary("ActivityCreated", {})
    assert summary == "Activity started"


def test_activity_progress_update_summary_names_the_update_kind():
    summary = _build_summary("ActivityProgressUpdateAdded", {"update_kind": "COMPLETED"})
    assert summary == "Progress update: Completed"


def test_activity_progress_update_summary_falls_back_without_a_kind():
    summary = _build_summary("ActivityProgressUpdateAdded", {})
    assert summary == "Progress update: Progress"


def test_activity_evidence_attached_summary():
    assert _build_summary("ActivityEvidenceAttached", {}) == "Photo evidence attached"


def test_all_three_activity_event_types_are_registered():
    assert "ActivityCreated" in EVENT_SUMMARY_BUILDERS
    assert "ActivityProgressUpdateAdded" in EVENT_SUMMARY_BUILDERS
    assert "ActivityEvidenceAttached" in EVENT_SUMMARY_BUILDERS
