"""Site Issue close-out target read service (wiring layer only).

Same shape and justification as runtime/reversal_query.py: adapts the
backend's PostgresProgressReadRepository.find_latest_by_status into a plain
async method the inbound journey can call before the graph runs (a node
must never query a repository itself -- see workflows/site_issue_close/
nodes.py's docstring). Never opens a write transaction, never mutates
state -- the close-out itself only ever happens after confirmation, via
application/progress/handlers.py's ExecuteConfirmedCloseSiteIssueHandler.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class SiteIssueCloseTarget(TypedDict):
    site_issue_id: str
    issue_type: str
    severity: str
    narrative: str | None


class SiteIssueTargetQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def find_latest(
        self,
        *,
        organization_id: str,
        project_id: str | None,
        site_id: str | None,
        statuses: tuple[str, ...],
        by_transition_time: bool = False,
    ) -> SiteIssueCloseTarget | None:
        """`by_transition_time` picks the issue whose status changed most
        recently rather than the one reported most recently -- see
        find_latest_by_status. Set only by the `reopen` action, whose "that's
        not actually fixed" points at the issue just closed."""
        from mesiri.infrastructure.postgres.repositories.progress import (
            PostgresProgressReadRepository,
        )

        async with self._db.transaction() as conn:
            repo = PostgresProgressReadRepository(conn)
            row = await repo.find_latest_by_status(
                uuid.UUID(organization_id),
                uuid.UUID(project_id) if project_id else None,
                uuid.UUID(site_id) if site_id else None,
                statuses,
                by_transition_time=by_transition_time,
            )
        if row is None:
            return None
        return SiteIssueCloseTarget(
            site_issue_id=str(row["id"]),
            issue_type=row["issue_type"],
            severity=row["severity"],
            narrative=row["narrative"],
        )
