"""REST API for escalations (#10 Human Review).

Mounted at /escalations so:
  GET   /escalations              list pending escalations
  GET   /escalations/{id}         get one escalation's full snapshot
  POST  /escalations/{id}/resolve record a human's decision

An escalation is a durable review record, not a re-triggerable draft --
resolving one records a decision (free-text note), it does not replay
anything automatically. See migration 0453's docstring.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.authorization.context import AuthorizationContext
from mesiri.domains.projects.router import get_auth_context
from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.repositories.escalations import PostgresEscalationRepository

router = APIRouter(prefix="/escalations", tags=["escalations"])


class ResolveEscalationRequest(BaseModel):
    resolution_note: str


@router.get("")
async def list_pending_escalations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresEscalationRepository(conn)
    items, total = await repo.list_pending(
        organization_id=auth_context.organization_id, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


@router.get("/{escalation_id}")
async def get_escalation(
    escalation_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresEscalationRepository(conn)
    escalation = await repo.get(
        organization_id=auth_context.organization_id, escalation_id=escalation_id
    )
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return escalation


@router.post("/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: uuid.UUID,
    req: ResolveEscalationRequest,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresEscalationRepository(conn)
    resolved = await repo.resolve(
        organization_id=auth_context.organization_id,
        escalation_id=escalation_id,
        resolved_by_user_id=auth_context.user_id,
        resolution_note=req.resolution_note,
    )
    if not resolved:
        raise HTTPException(
            status_code=404, detail="Escalation not found or already resolved"
        )
    return {"status": "success"}
