"""Open-activity lookup for the Activity Continuation workflow (wiring layer only).

Same shape and justification as runtime/vendor_query.py: adapts a plain read
query into an async method the inbound journey can call before the graph
runs (a node must never query a repository itself -- see
workflows/runtime.py). Never opens a write transaction.

Implements the "find today's open activity for this reporter/site" lookup
docs/execution/DAILY_REPORTING_PLAN.md's P10/§1B.2 describe: a continuation
message ("finished plastering", "completed another 40 sqm") should never
have to name which activity it means when there is exactly one plausible
answer.

Scoped by reporter AND site, not just project: two engineers on the same
site must never have their activities conflated, and neither should two
sites on the same project. If more than one open activity matches (rare --
one person with several simultaneous activities on the same site), the most
recently updated one wins rather than asking -- a deliberate P10
simplification for V1; a real disambiguation prompt is future work if this
proves to happen often enough to matter.

Deliberately NOT filtered by "today's date": an IN_PROGRESS activity that
spans past midnight (a late finish, or simply never marked complete) must
still be continuable the next message regardless of the server's calendar
date -- the same class of bug canonicalization/occurred_date.py's docstring
describes for a *stated* date applies here to an *inferred* one. "Open"
(status) is the only signal that matters; recency (`updated_at`) only breaks
ties when more than one activity is open at once.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase

#: Activities in either of these states are still "open" for continuation.
#: COMPLETED/STOPPED activities are not offered -- a message about finished
#: work with no open activity falls through to activity_creation instead
#: (see workflows/site_update/'s handling of no_open_activity).
_OPEN_STATUSES = ("PLANNED", "IN_PROGRESS")


class ActivityQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def find_open_activity(
        self,
        *,
        organization_id: str,
        site_id: str | None,
        reported_by_user_id: str | None,
    ) -> dict[str, Any] | None:
        """The open activity for this reporter on this site, if exactly (or
        most plausibly) one exists. None when there is nothing to continue --
        a normal, common outcome, not a failure."""
        if not site_id or not reported_by_user_id:
            return None

        import sqlalchemy as sa

        try:
            org_id = uuid.UUID(organization_id)
            site_uuid = uuid.UUID(site_id)
            reporter_uuid = uuid.UUID(reported_by_user_id)
        except (TypeError, ValueError):
            return None

        activities = sa.table(
            "activities",
            sa.column("id"),
            sa.column("organization_id"),
            sa.column("site_id"),
            sa.column("reported_by_user_id"),
            sa.column("status"),
            sa.column("work_type"),
            sa.column("narrative"),
            sa.column("deleted_at"),
            sa.column("updated_at"),
        )

        query = (
            sa.select(
                activities.c.id,
                activities.c.work_type,
                activities.c.narrative,
                activities.c.status,
            )
            .where(
                activities.c.organization_id == org_id,
                activities.c.site_id == site_uuid,
                activities.c.reported_by_user_id == reporter_uuid,
                activities.c.status.in_(_OPEN_STATUSES),
                activities.c.deleted_at.is_(None),
            )
            .order_by(activities.c.updated_at.desc())
            .limit(1)
        )

        async with self._db.transaction() as conn:
            row = (await conn.execute(query)).mappings().first()

        if row is None:
            return None
        return {
            "activity_id": str(row["id"]),
            "work_type": row["work_type"],
            "narrative": row["narrative"],
            "status": row["status"],
        }
