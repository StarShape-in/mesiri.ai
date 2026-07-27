"""Workforce register lookups for the Labour attendance workflow.

The matching node needs candidates from the register to decide whether a
reported "Ravi" is someone already known (Labour plan principle P4 — never
identified by name alone). A node must never query a repository itself (see
workflows/runtime.py), so the read happens here and is seeded into the event's
fields by runtime/inbound_journey.py's `_seed_worker_candidates`, exactly as
money accounts are for expense.

**2026-07-27: this is now backed by the real database.** It shipped as a stub
while Labour was built conversation-first, and the stub is kept below only for
local/test use where no database exists. The register (``workforce_workers``)
is real, has dashboard CRUD (domains/workforce/router.py), and attendance
history (``labour_attendance_lines``) is real too — so "has this worker been
seen on this site before", the single strongest corroborating signal matching
has, is now a genuine answer rather than a configured guess.

Why that signal matters enough to compute here rather than defer: P4 caps a
name-only match below auto-accept by construction, so without corroboration
*every* named worker asks a question. `seen_on_site` / `seen_on_project` are
what let a returning worker match silently, which is what keeps a ten-worker
report to zero questions instead of ten (P9).

Two properties this deliberately preserves from the stub era:

- **Read-only.** There is no write path here at all. Attendance never writes
  the register (principle P1); promotion is a separate, explicitly confirmed
  act performed from the dashboard.
- **Never invents a worker.** An organization with an empty register gets an
  empty list, every named worker becomes a temporary worker, and nothing is
  asked (principle P3). That is correct behaviour, not a degraded mode.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase

logger = logging.getLogger(__name__)

STUB_WORKERS_ENV = "MESIRI_LABOUR__STUB_WORKERS"

#: Only active workers are offered as candidates. A retired worker must never
#: be silently matched onto a new report -- if they genuinely returned, that
#: is a deliberate reactivation on the dashboard, not something attendance
#: capture should infer.
_ACTIVE = "active"

#: Upper bound on candidates handed to matching. Matching is O(candidates x
#: reported names) pure scoring, and a prompt can only show 10 options anyway
#: (channel/replies.py's list limit), so reading an entire 2000-worker register
#: into memory for one report would be waste, not thoroughness.
_MAX_CANDIDATES = 200


class WorkforceQueryService(Protocol):
    """Read-only access to the workforce register."""

    async def list_worker_candidates(
        self,
        *,
        organization_id: str,
        project_id: str | None = None,
        site_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Registered workers plausibly on this project/site.

        Each entry matches `domains/workforce/matching.WorkerCandidate`'s
        shape: worker_id, name, and optionally trade, contractor,
        seen_on_site, seen_on_project.
        """
        ...


class PostgresWorkforceQueryService:
    """Reads the real register, annotated with where each worker has worked."""

    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def list_worker_candidates(
        self,
        *,
        organization_id: str,
        project_id: str | None = None,
        site_id: str | None = None,
    ) -> list[dict[str, Any]]:
        import sqlalchemy as sa

        try:
            org_id = uuid.UUID(organization_id)
        except (TypeError, ValueError):
            return []

        # seen_on_site / seen_on_project are computed in SQL rather than by
        # reading attendance history into Python: the register is the small
        # table and its history is the large one, so the join belongs in the
        # database. EXISTS (not a count) because matching only asks whether
        # the worker has been here before, never how often.
        lines = sa.table(
            "labour_attendance_lines",
            sa.column("worker_id"),
            sa.column("report_id"),
        )
        reports = sa.table(
            "labour_attendance_reports",
            sa.column("id"),
            sa.column("project_id"),
            sa.column("site_id"),
            sa.column("organization_id"),
        )
        workers = sa.table(
            "workforce_workers",
            sa.column("id"),
            sa.column("organization_id"),
            sa.column("name"),
            sa.column("trade"),
            sa.column("contractor"),
            sa.column("status"),
        )

        def _worked_in(scope_column, scope_value: uuid.UUID):
            return (
                sa.select(sa.literal(1))
                .select_from(lines.join(reports, lines.c.report_id == reports.c.id))
                .where(
                    lines.c.worker_id == workers.c.id,
                    reports.c.organization_id == org_id,
                    scope_column == scope_value,
                )
                .exists()
            )

        seen_on_site: Any = sa.literal(False)
        seen_on_project: Any = sa.literal(False)
        if site_id:
            try:
                seen_on_site = _worked_in(reports.c.site_id, uuid.UUID(site_id))
            except (TypeError, ValueError):
                pass
        if project_id:
            try:
                seen_on_project = _worked_in(reports.c.project_id, uuid.UUID(project_id))
            except (TypeError, ValueError):
                pass

        query = (
            sa.select(
                workers.c.id,
                workers.c.name,
                workers.c.trade,
                workers.c.contractor,
                seen_on_site.label("seen_on_site"),
                seen_on_project.label("seen_on_project"),
            )
            .where(
                workers.c.organization_id == org_id,
                workers.c.status == _ACTIVE,
            )
            .order_by(workers.c.name)
            .limit(_MAX_CANDIDATES)
        )

        async with self._db.transaction() as conn:
            rows = (await conn.execute(query)).mappings().all()

        return [
            {
                "worker_id": str(row["id"]),
                "name": row["name"],
                "trade": row["trade"],
                "contractor": row["contractor"],
                "seen_on_site": bool(row["seen_on_site"]),
                "seen_on_project": bool(row["seen_on_project"]),
            }
            for row in rows
        ]


class StubWorkforceQueryService:
    """Empty register unless a roster is configured — local/test use only.

    Superseded in production by PostgresWorkforceQueryService above. Kept
    because it is genuinely useful for exercising matching without a database,
    and because its default (empty) is the honest answer rather than a
    fabrication.

    ``worker_id`` must be a real UUID, not a short label like ``"w-ravi"`` --
    once a line matches, its worker_id flows into
    ``LabourAttendanceLine.worker_id`` (application/labour/mapper.py), a
    ``CanonicalUuid`` field, and a non-UUID value fails command validation::

        MESIRI_LABOUR__STUB_WORKERS='[
          {"worker_id": "11111111-1111-4111-8111-111111111111", "name": "Ravi Kumar",
           "trade": "mason", "contractor": "Kumar Team", "seen_on_site": true}
        ]'
    """

    def __init__(self, roster: list[dict[str, Any]] | None = None) -> None:
        self._roster = roster if roster is not None else _roster_from_env()

    async def list_worker_candidates(
        self,
        *,
        organization_id: str,
        project_id: str | None = None,
        site_id: str | None = None,
    ) -> list[dict[str, Any]]:
        # Not scoped by org/project/site: a configured test roster is for one
        # tenant on one machine by construction. The Postgres reader above
        # scopes on organization and computes the site/project signals for
        # real -- a worker from another organization never appears there.
        return list(self._roster)


def _roster_from_env() -> list[dict[str, Any]]:
    """Parse the opt-in stub roster, or return empty.

    Never raises: a malformed roster degrades to an empty register (every
    worker temporary, nothing asked) rather than taking down attendance
    capture entirely. A bad env var is a config mistake, not a reason a site
    cannot report who turned up.
    """
    raw = os.environ.get(STUB_WORKERS_ENV, "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        logger.warning("labour.stub_roster_invalid_json env=%s", STUB_WORKERS_ENV)
        return []
    if not isinstance(parsed, list):
        logger.warning("labour.stub_roster_not_a_list env=%s", STUB_WORKERS_ENV)
        return []

    roster: list[dict[str, Any]] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        worker_id = entry.get("worker_id") or entry.get("id")
        name = entry.get("name")
        if not worker_id or not name:
            continue
        roster.append(
            {
                "worker_id": str(worker_id),
                "name": str(name),
                "trade": entry.get("trade"),
                "contractor": entry.get("contractor"),
                "seen_on_site": bool(entry.get("seen_on_site")),
                "seen_on_project": bool(entry.get("seen_on_project")),
            }
        )
    if roster:
        logger.warning(
            "labour.stub_roster_active count=%d -- workforce register is STUBBED, "
            "not from the database",
            len(roster),
        )
    return roster
