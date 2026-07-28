"""Site Issue's timeline entry — the summary text and the aggregate registration.

Pure/offline tests only (no live database — see the integration suite for
that). Pins the fix for the "blocker" timeline category being permanently
unreachable: site_issues was never registered in AGGREGATE_TABLES and never
wrote outbox_events, so no SiteIssue* event type could ever appear in
timeline_entries.
"""

from __future__ import annotations

from mesiri.events.consumers.timeline_projector import (
    AGGREGATE_TABLES,
    EVENT_SUMMARY_BUILDERS,
    _build_summary,
)


def test_site_issue_is_a_registered_aggregate():
    assert "site_issue" in AGGREGATE_TABLES


def test_site_issue_table_exposes_occurred_at_directly():
    """Unlike activities (occurred_date/occurred_time), site_issues already
    has a single occurred_at timestamp column — no alias needed, just the
    projector's alternate branch for tables shaped this way."""
    table = AGGREGATE_TABLES["site_issue"]
    assert "occurred_at" in table.c
    assert "occurred_date" not in table.c


def test_site_issue_reported_summary_names_type_and_severity():
    summary = _build_summary(
        "SiteIssueReported", {"issue_type": "EQUIPMENT_BREAKDOWN", "severity": "HIGH"}
    )
    assert summary == "Equipment Breakdown reported (High)"


def test_site_issue_reported_summary_falls_back_without_type_or_severity():
    summary = _build_summary("SiteIssueReported", {})
    assert summary == "Issue reported"


def test_site_issue_acknowledged_summary():
    assert _build_summary("SiteIssueAcknowledged", {}) == "Site issue acknowledged"


def test_site_issue_resolved_summary():
    assert _build_summary("SiteIssueResolved", {}) == "Site issue resolved"


def test_site_issue_wont_fix_summary():
    assert _build_summary("SiteIssueWontFix", {}) == "Site issue marked as won't fix"


def test_all_four_site_issue_event_types_are_registered():
    assert "SiteIssueReported" in EVENT_SUMMARY_BUILDERS
    assert "SiteIssueAcknowledged" in EVENT_SUMMARY_BUILDERS
    assert "SiteIssueResolved" in EVENT_SUMMARY_BUILDERS
    assert "SiteIssueWontFix" in EVENT_SUMMARY_BUILDERS
