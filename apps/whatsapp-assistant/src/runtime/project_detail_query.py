"""Project team-size lookup for the project.detail_query workflow
("give me all details of this project").

Everything else that workflow needs (project/site name, code, location,
status, the site list) comes for free off `ActorIdentity.projects`/`.sites`
-- already resolved once per inbound message (see backend/postgres/actor.py)
-- and every operational rollup (open issues, labour, activities, stock,
spend) is composed from the existing runtime/*_query.py services. The one
genuinely new read is this: nothing in the codebase counts a project's
`project_members` rows today.

Same shape and justification as runtime/dpr_request_query.py: a plain async
method the assistant can call so a node/seed step never queries a
repository itself.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class ProjectDetailQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def count_members(self, *, project_id: str) -> int:
        """Explicit project_members rows for this project. Deliberately NOT
        the same as "everyone who can reach this project" -- an org-wide
        role or an access_policy 'all_projects' bypass never gets a
        project_members row (see mesiri.authorization.roles.is_org_wide),
        so this is a lower bound ("N assigned team members"), not a claim
        about total reach. Good enough for a WhatsApp summary line; the
        dashboard's Members tab is the source of truth for exact access."""
        import sqlalchemy as sa

        try:
            proj_uuid = uuid.UUID(project_id)
        except (TypeError, ValueError):
            return 0

        async with self._db.transaction() as conn:
            count = (
                await conn.execute(
                    sa.text("SELECT count(*) FROM project_members WHERE project_id = :project_id"),
                    {"project_id": proj_uuid},
                )
            ).scalar_one()
        return int(count)
