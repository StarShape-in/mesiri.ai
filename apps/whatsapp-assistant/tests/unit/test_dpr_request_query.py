"""DprRequestQueryService's guard clauses -- only the paths that return
before ever touching the database are unit-testable without a live
Postgres (the real query is exercised by CI's live-Postgres integration
lane, not here, same split as test_actor_reader_notifications.py)."""

from __future__ import annotations

import datetime

from runtime.dpr_request_query import DprRequestQueryService

TODAY = datetime.date(2026, 7, 27)


async def test_missing_project_id_returns_not_generated_without_touching_the_db():
    service = DprRequestQueryService(db="unused -- must never be touched")
    result = await service.find_report(
        organization_id="11111111-1111-4111-8111-111111111111",
        project_id=None,
        site_id="44444444-4444-4444-8444-444444444444",
        report_date=TODAY,
    )
    assert result == {"status": "not_generated", "object_key": None, "code": None}


async def test_missing_site_id_returns_not_generated_without_touching_the_db():
    service = DprRequestQueryService(db="unused -- must never be touched")
    result = await service.find_report(
        organization_id="11111111-1111-4111-8111-111111111111",
        project_id="33333333-3333-4333-8333-333333333333",
        site_id=None,
        report_date=TODAY,
    )
    assert result == {"status": "not_generated", "object_key": None, "code": None}


async def test_malformed_organization_id_returns_not_generated_without_touching_the_db():
    service = DprRequestQueryService(db="unused -- must never be touched")
    result = await service.find_report(
        organization_id="not-a-uuid",
        project_id="33333333-3333-4333-8333-333333333333",
        site_id="44444444-4444-4444-8444-444444444444",
        report_date=TODAY,
    )
    assert result == {"status": "not_generated", "object_key": None, "code": None}
