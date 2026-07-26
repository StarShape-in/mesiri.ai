"""Workforce register lookups for the Labour attendance workflow.

The matching node needs candidates from the register to decide whether a
reported "Ravi" is someone already known (Labour plan principle P4 — never
identified by name alone). A node must never query a repository itself (see
workflows/runtime.py), so the read happens here and is seeded into the event's
fields by runtime/inbound_journey.py's `_seed_worker_candidates`, exactly as
money accounts are for expense.

**The register has no tables yet.** Labour is being built conversation-first
by explicit decision (2026-07-26): prove the assistant understands attendance,
matches workers and previews correctly, *before* committing to a schema. So
this ships a stub, and Phase 5 replaces it with a Postgres reader behind the
same call.

The stub's default is an **empty register**, and that is a deliberate, honest
default rather than a placeholder:

- An organization that has never recorded attendance genuinely has no
  register, so empty is the truthful answer on day one.
- With no candidates, every named worker resolves to a temporary worker and
  the workflow asks nothing. That is correct behaviour (principle P3), not a
  degraded mode.
- Nothing is ever invented. A stub that fabricated plausible workers would
  make matching *look* like it worked while attaching real attendance to
  people who do not exist — the exact class of corruption P4 exists to
  prevent.

To actually exercise matching before the tables land, set a roster explicitly
via ``MESIRI_LABOUR__STUB_WORKERS`` (JSON). Opt-in, visible in config, and
impossible to mistake for real data::

    MESIRI_LABOUR__STUB_WORKERS='[
      {"worker_id": "w-ravi", "name": "Ravi Kumar", "trade": "mason",
       "contractor": "Kumar Team", "seen_on_site": true},
      {"worker_id": "w-arun", "name": "Arun", "trade": "painter"}
    ]'

Attendance must never write this register (principle P1) — note there is no
write path here at all, and the stub deliberately does not "remember" workers
from confirmed reports. Promotion into the register is a separate, explicitly
confirmed act, and building the stub to auto-learn would quietly break the
very rule the workflow is being validated against.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Protocol

logger = logging.getLogger(__name__)

STUB_WORKERS_ENV = "MESIRI_LABOUR__STUB_WORKERS"


class WorkforceQueryService(Protocol):
    """Read-only access to the workforce register.

    Phase 5 supplies a Postgres implementation; the signature is what the
    seeding step needs and nothing more, so the real reader can be dropped in
    without touching inbound_journey.
    """

    async def list_worker_candidates(
        self,
        *,
        organization_id: str,
        project_id: str | None = None,
        site_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Registered workers plausibly on this project/site, best-first.

        Each entry matches `domains/workforce/matching.WorkerCandidate`'s
        shape: worker_id, name, and optionally trade, contractor,
        seen_on_site, seen_on_project.
        """
        ...


class StubWorkforceQueryService:
    """Empty register unless a roster is configured. See the module docstring."""

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
        # tenant on one machine by construction. The real reader must scope on
        # all three -- a worker from another organization must never appear as
        # a candidate.
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
