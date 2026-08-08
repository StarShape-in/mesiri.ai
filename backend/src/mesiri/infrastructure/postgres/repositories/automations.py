"""PostgreSQL repository for automations -- user-defined recurring schedules.

The only file permitted to hold SQL for the `automations` table (capability-
boundary convention, mirrors infrastructure/postgres/repositories/dpr.py).
Both write paths -- the dashboard's direct REST create/update and the
WhatsApp confirmed-command path (application/automations/create_*.py) --
call `create()` here rather than each holding their own INSERT, so the
column list only ever needs to change in one place.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresAutomationRepository:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        project_id: uuid.UUID | None,
        site_id: uuid.UUID | None,
        action: str,
        audience: str,
        audience_user_ids: list[str] | None,
        audience_role: str | None,
        message: str | None,
        frequency: str,
        day_of_week: int | None,
        time_of_day: str,
        timezone: str,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        import json

        automation_id = uuid.uuid4()
        await self._conn.execute(
            text(
                """
                INSERT INTO automations (
                    id, organization_id, project_id, site_id, action, audience,
                    audience_user_ids, audience_role, message, frequency,
                    day_of_week, time_of_day, timezone, enabled, created_by
                ) VALUES (
                    :id, :organization_id, :project_id, :site_id, :action, :audience,
                    CAST(:audience_user_ids AS jsonb), :audience_role, :message, :frequency,
                    :day_of_week, :time_of_day, :timezone, true, :created_by
                )
                """
            ),
            {
                "id": automation_id,
                "organization_id": organization_id,
                "project_id": project_id,
                "site_id": site_id,
                "action": action,
                "audience": audience,
                "audience_user_ids": json.dumps(audience_user_ids) if audience_user_ids else None,
                "audience_role": audience_role,
                "message": message,
                "frequency": frequency,
                "day_of_week": day_of_week,
                "time_of_day": time_of_day,
                "timezone": timezone,
                "created_by": created_by,
            },
        )
        row = await self.get(organization_id=organization_id, automation_id=automation_id)
        assert row is not None
        return row

    async def list_for_org(self, *, organization_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self._conn.execute(
                text(
                    "SELECT * FROM automations WHERE organization_id = :organization_id "
                    "ORDER BY created_at DESC"
                ),
                {"organization_id": organization_id},
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    async def get(
        self, *, organization_id: uuid.UUID, automation_id: uuid.UUID
    ) -> dict[str, Any] | None:
        row = (
            await self._conn.execute(
                text(
                    "SELECT * FROM automations WHERE organization_id = :organization_id "
                    "AND id = :id"
                ),
                {"organization_id": organization_id, "id": automation_id},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def update(
        self, *, organization_id: uuid.UUID, automation_id: uuid.UUID, fields: dict[str, Any]
    ) -> bool:
        """`fields` is a pre-validated column->value map (built by the
        router from whichever fields the request actually set) -- this
        method does no shape validation of its own, matching dpr.py's
        update_project's identical split between router-level field
        selection and repository-level SQL."""
        if not fields:
            return True
        import json

        allowed = {
            "action", "audience", "audience_user_ids", "audience_role", "message",
            "frequency", "day_of_week", "time_of_day", "timezone", "enabled",
            "project_id", "site_id",
        }
        set_clauses = []
        params: dict[str, Any] = {"organization_id": organization_id, "id": automation_id}
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "audience_user_ids":
                set_clauses.append(f"{key} = CAST(:{key} AS jsonb)")
                params[key] = json.dumps(value) if value else None
            else:
                set_clauses.append(f"{key} = :{key}")
                params[key] = value
        if not set_clauses:
            return True
        set_clauses.append("updated_at = now()")
        result = await self._conn.execute(
            text(
                f"UPDATE automations SET {', '.join(set_clauses)} "
                "WHERE organization_id = :organization_id AND id = :id"
            ),
            params,
        )
        return result.rowcount > 0

    async def delete(self, *, organization_id: uuid.UUID, automation_id: uuid.UUID) -> bool:
        result = await self._conn.execute(
            text(
                "DELETE FROM automations WHERE organization_id = :organization_id AND id = :id"
            ),
            {"organization_id": organization_id, "id": automation_id},
        )
        return result.rowcount > 0

    async def list_enabled(self) -> list[dict[str, Any]]:
        """Every enabled automation across every organization -- the
        runner's own scope narrowing (per-org active-status check) happens
        in the caller, mirroring run_dpr_generation.py's identical split."""
        rows = (
            await self._conn.execute(
                text("SELECT * FROM automations WHERE enabled = true")
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    async def mark_run(self, *, automation_id: uuid.UUID, ran_on: date) -> None:
        await self._conn.execute(
            text(
                "UPDATE automations SET last_run_on = :ran_on, updated_at = now() WHERE id = :id"
            ),
            {"ran_on": ran_on, "id": automation_id},
        )
