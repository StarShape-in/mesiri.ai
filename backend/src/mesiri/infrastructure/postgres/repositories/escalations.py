"""PostgreSQL repository for escalations (#10 Human Review).

The only file permitted to hold SQL for the escalations table -- same
capability-boundary convention as backend/postgres/actor.py. Takes a
connection, never opens its own transaction (the caller -- a FastAPI route
or the WhatsApp-side wiring service -- owns that boundary).
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresEscalationRepository:
    def __init__(self, conn: AsyncConnection) -> None:
        self.conn = conn

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        correlation_id: str,
        reason: str,
        snapshot: dict[str, Any],
    ) -> uuid.UUID:
        from sqlalchemy import text

        escalation_id = uuid.uuid4()
        await self.conn.execute(
            text(
                "INSERT INTO escalations "
                "(id, organization_id, correlation_id, reason, snapshot, status) "
                "VALUES (:id, :organization_id, :correlation_id, :reason, "
                "CAST(:snapshot AS jsonb), 'pending')"
            ),
            {
                "id": escalation_id,
                "organization_id": organization_id,
                "correlation_id": correlation_id,
                "reason": reason,
                "snapshot": json.dumps(snapshot),
            },
        )
        return escalation_id

    async def list_pending(
        self, *, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        from sqlalchemy import text

        total_row = (
            await self.conn.execute(
                text(
                    "SELECT COUNT(*) AS total FROM escalations "
                    "WHERE organization_id = :organization_id AND status = 'pending'"
                ),
                {"organization_id": organization_id},
            )
        ).mappings().first()
        total = total_row["total"] if total_row else 0

        rows = (
            (
                await self.conn.execute(
                    text(
                        "SELECT e.id, e.correlation_id, e.reason, e.snapshot, e.status, "
                        "e.assigned_to_user_id, u.name AS assigned_to_name, e.created_at "
                        "FROM escalations e "
                        "LEFT JOIN users u ON u.id = e.assigned_to_user_id "
                        "WHERE e.organization_id = :organization_id AND e.status = 'pending' "
                        "ORDER BY e.created_at ASC "
                        "LIMIT :limit OFFSET :offset"
                    ),
                    {"organization_id": organization_id, "limit": limit, "offset": offset},
                )
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows], total

    async def get(
        self, *, organization_id: uuid.UUID, escalation_id: uuid.UUID
    ) -> dict[str, Any] | None:
        from sqlalchemy import text

        row = (
            await self.conn.execute(
                text(
                    "SELECT id, correlation_id, reason, snapshot, status, "
                    "assigned_to_user_id, resolution_note, resolved_by_user_id, "
                    "resolved_at, created_at "
                    "FROM escalations WHERE organization_id = :organization_id AND id = :id"
                ),
                {"organization_id": organization_id, "id": escalation_id},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def resolve(
        self,
        *,
        organization_id: uuid.UUID,
        escalation_id: uuid.UUID,
        resolved_by_user_id: uuid.UUID,
        resolution_note: str,
    ) -> bool:
        """Marks a PENDING escalation resolved. Returns False (no-op) if it
        was already resolved or doesn't exist -- resolving is a one-way,
        idempotent-safe transition, never a re-triggerable action."""
        from sqlalchemy import text

        result = await self.conn.execute(
            text(
                "UPDATE escalations SET status = 'resolved', "
                "resolution_note = :note, resolved_by_user_id = :resolved_by, "
                "resolved_at = now() "
                "WHERE organization_id = :organization_id AND id = :id AND status = 'pending'"
            ),
            {
                "organization_id": organization_id,
                "id": escalation_id,
                "note": resolution_note,
                "resolved_by": resolved_by_user_id,
            },
        )
        return result.rowcount > 0
