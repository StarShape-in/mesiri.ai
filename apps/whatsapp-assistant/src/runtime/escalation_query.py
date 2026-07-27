"""Escalation-create service (#10 Human Review, wiring layer only).

Same shape and justification as runtime/evidence_query.py: adapts the
backend's PostgresEscalationRepository into a plain async method the
assistant can call directly. Unlike a confirmed action, creating an
escalation is never behind a YES/NO -- it fires the moment #7 Low-Confidence
Routing decides ESCALATE (nothing usable was extracted at all), before any
workflow or draft exists to confirm.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class EscalationCreateService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def create(
        self,
        *,
        organization_id: str,
        correlation_id: str,
        reason: str,
        snapshot: dict[str, Any],
    ) -> str:
        import uuid

        from mesiri.infrastructure.postgres.repositories.escalations import (
            PostgresEscalationRepository,
        )

        async with self._db.transaction() as conn:
            repo = PostgresEscalationRepository(conn)
            escalation_id = await repo.create(
                organization_id=uuid.UUID(organization_id),
                correlation_id=correlation_id,
                reason=reason,
                snapshot=snapshot,
            )
        return str(escalation_id)
