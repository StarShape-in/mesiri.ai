"""Labour's attendance-photo gallery — the repository query, offline.

Compiled-SQL assertions, not a live database (same approach and the same
limitation as test_workforce_seeding.py's PostgresWorkforceQueryService
tests): these pin the three things most likely to leak data across tenants
or projects if got wrong -- organization scoping, the project_ids SET filter
(not a single id, which cannot express "these three projects but not that
one"), and that the join goes through the report row rather than trusting
anything on the attachment itself.
"""

from __future__ import annotations

import uuid

from mesiri.infrastructure.postgres.repositories.workforce import (
    PostgresWorkforceReadRepository,
)

ORG = uuid.UUID("11111111-1111-4111-8111-111111111111")
PRJ_A = uuid.UUID("33333333-3333-4333-8333-333333333333")
PRJ_B = uuid.UUID("55555555-5555-4555-8555-555555555555")
SITE = uuid.UUID("44444444-4444-4444-8444-444444444444")


class _CapturingConn:
    def __init__(self):
        self.compiled: str | None = None
        self.calls: list[str] = []

    async def execute(self, query, *args, **kwargs):
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        self.compiled = compiled
        self.calls.append(compiled)

        class _R:
            def mappings(self_inner):
                class _M:
                    def all(self_m):
                        return []

                return _M()

        return _R()


async def _compiled(**kwargs) -> list[str]:
    conn = _CapturingConn()
    repo = PostgresWorkforceReadRepository(conn)
    await repo.list_attachments_for_organization(ORG, **kwargs)
    return conn.calls


async def test_the_query_scopes_to_the_organization():
    calls = await _compiled()
    first_query = calls[0]
    assert "labour_attendance_reports.organization_id" in first_query
    assert ORG.hex in first_query


async def test_a_project_ids_set_filters_to_exactly_those_projects():
    """A single project_id can't express "these two projects but not a
    third" -- the whole reason this takes a set, matching list_reports."""
    calls = await _compiled(project_ids={PRJ_A, PRJ_B})
    first_query = calls[0]
    assert "labour_attendance_reports.project_id IN" in first_query
    assert PRJ_A.hex in first_query
    assert PRJ_B.hex in first_query


async def test_no_project_ids_means_no_project_filter_at_all():
    """None is portfolio-wide access, not "match nothing" -- same convention
    list_reports already uses for a caller who can see the whole org."""
    calls = await _compiled()
    assert "project_id IN" not in calls[0]
    assert "project_id =" not in calls[0]


async def test_the_join_goes_through_the_report_not_the_attachment():
    """An attachment carries no organization_id of its own -- the join to
    labour_attendance_reports is what makes tenant scoping possible at all."""
    calls = await _compiled()
    assert "JOIN labour_attendance_reports" in calls[0]


async def test_site_and_date_range_narrow_the_query():
    calls = await _compiled(
        site_id=SITE,
        start_date=__import__("datetime").date(2026, 7, 1),
        end_date=__import__("datetime").date(2026, 7, 31),
    )
    first_query = calls[0]
    assert "labour_attendance_reports.site_id" in first_query
    assert "labour_attendance_reports.occurred_date >=" in first_query
    assert "labour_attendance_reports.occurred_date <=" in first_query


async def test_an_empty_result_never_queries_for_headcount_totals():
    """No attachments means nothing to caption -- the second query (per-report
    headcount/cost) must not fire on an empty result, which would be a wasted
    round trip on every gallery page with no photos in range."""
    calls = await _compiled()
    assert len(calls) == 1
