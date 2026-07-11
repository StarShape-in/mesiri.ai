from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.authorization.context import AuthorizationContext
from mesiri.domains.materials.responses import (
    MaterialReceiptsListResponse,
    MaterialStockResponse,
    MaterialUsageListResponse,
)
from mesiri.domains.projects.router import get_auth_context
from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.repositories.materials import PostgresMaterialReadRepository

router = APIRouter(prefix="/materials", tags=["materials"])


def _site_filter_denied(
    auth_context: AuthorizationContext,
    project_id: uuid.UUID | None,
    site_id: uuid.UUID | None,
) -> bool:
    """True if the requested site_id filter must be denied under the caller's site scope.

    site_id filters are only authorization-checked when a single project_id is
    also known — site access is resolved per-project (AccessPolicy nests
    siteAccess under each project grant). A site_id without a project_id can
    only be trusted for org-wide (all_projects) callers; custom-scoped callers
    are denied in that ambiguous case rather than leaking cross-project data.
    """
    if site_id is None:
        return False
    if project_id is None:
        return not auth_context.project_scope.grants_all_org_projects
    site_scope = auth_context.site_scope_for_project(project_id)
    if site_scope.grants_all_sites:
        return False
    return site_id not in site_scope.site_ids


async def _publish_outbox_event(
    conn: AsyncConnection,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Write an outbox_events row on the caller's connection/transaction.

    Mobile-direct writes have no correlation_id concept today, so callers
    normally omit it. The timeline projector (mesiri.events.consumers.
    timeline_projector) drains this table into timeline_entries.
    """
    from sqlalchemy import text

    await conn.execute(
        text(
            "INSERT INTO outbox_events "
            "(id, aggregate_type, aggregate_id, event_type, payload, correlation_id) "
            "VALUES (:id, :aggregate_type, :aggregate_id, :event_type, "
            "CAST(:payload AS jsonb), :correlation_id)"
        ),
        {
            "id": uuid.uuid4(),
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "payload": json.dumps(payload),
            "correlation_id": correlation_id,
        },
    )


@router.get("/inflows", response_model=MaterialReceiptsListResponse)
async def list_inflows(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    material_name: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List material inflows (receipts) within the user's organization and project scope."""
    if project_id is not None:
        if not auth_context.project_scope.grants_all_org_projects:
            if project_id not in auth_context.project_scope.project_ids:
                return {"items": [], "total": 0}
        project_ids = {project_id}
    else:
        if not auth_context.project_scope.grants_all_org_projects:
            if not auth_context.project_scope.project_ids:
                return {"items": [], "total": 0}
            project_ids = auth_context.project_scope.project_ids
        else:
            project_ids = None

    if _site_filter_denied(auth_context, project_id, site_id):
        return {"items": [], "total": 0}

    repo = PostgresMaterialReadRepository(conn)
    items, total = await repo.list_receipts(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
        material_name=material_name,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/outflows", response_model=MaterialUsageListResponse)
async def list_outflows(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    material_name: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List material outflows (usages) within the user's organization and project scope."""
    if project_id is not None:
        if not auth_context.project_scope.grants_all_org_projects:
            if project_id not in auth_context.project_scope.project_ids:
                return {"items": [], "total": 0}
        project_ids = {project_id}
    else:
        if not auth_context.project_scope.grants_all_org_projects:
            if not auth_context.project_scope.project_ids:
                return {"items": [], "total": 0}
            project_ids = auth_context.project_scope.project_ids
        else:
            project_ids = None

    if _site_filter_denied(auth_context, project_id, site_id):
        return {"items": [], "total": 0}

    repo = PostgresMaterialReadRepository(conn)
    items, total = await repo.list_usage(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
        material_name=material_name,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/inventory", response_model=list[MaterialStockResponse])
async def list_inventory(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Get aggregated material inventory (stock levels) within the organization and scope."""
    if project_id is not None:
        if not auth_context.project_scope.grants_all_org_projects:
            if project_id not in auth_context.project_scope.project_ids:
                return []
        project_ids = {project_id}
    else:
        if not auth_context.project_scope.grants_all_org_projects:
            if not auth_context.project_scope.project_ids:
                return []
            project_ids = auth_context.project_scope.project_ids
        else:
            project_ids = None

    if _site_filter_denied(auth_context, project_id, site_id):
        return []

    repo = PostgresMaterialReadRepository(conn)
    levels = await repo.get_stock_levels(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
    )
    return levels


# ---------------------------------------------------------------------------
# Write Schemas & Endpoints
# ---------------------------------------------------------------------------
class MaterialInflowCreate(BaseModel):
    project_id: uuid.UUID
    site_id: uuid.UUID | None = None
    material_name: str
    quantity: Decimal
    unit: str
    supplier: str | None = None
    occurred_date: datetime.date


class MaterialOutflowCreate(BaseModel):
    project_id: uuid.UUID
    site_id: uuid.UUID | None = None
    material_name: str
    quantity: Decimal
    unit: str
    work_item: str | None = None
    occurred_date: datetime.date


@router.post("/inflows", status_code=201)
async def create_inflow(
    body: MaterialInflowCreate,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Log a material receipt/inflow directly from the mobile app."""
    # Verify project scope
    if not auth_context.project_scope.grants_all_org_projects:
        if body.project_id not in auth_context.project_scope.project_ids:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not authorized for this project")

    if _site_filter_denied(auth_context, body.project_id, body.site_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized for this site")

    from sqlalchemy import text

    row_id = uuid.uuid4()
    await conn.execute(
        text(
            "INSERT INTO material_receipts "
            "(id, organization_id, project_id, site_id, material_name, quantity, unit, "
            "supplier, occurred_date, occurred_date_source, source, created_by) "
            "VALUES (:id, :organization_id, :project_id, :site_id, :material_name, "
            ":quantity, :unit, :supplier, :occurred_date, 'reported', 'mobile', :created_by)"
        ),
        {
            "id": row_id,
            "organization_id": auth_context.organization_id,
            "project_id": body.project_id,
            "site_id": body.site_id,
            "material_name": body.material_name.strip(),
            "quantity": body.quantity,
            "unit": body.unit.strip(),
            "supplier": body.supplier.strip() if body.supplier else None,
            "occurred_date": body.occurred_date,
            "created_by": auth_context.user_id,
        },
    )
    await _publish_outbox_event(
        conn,
        aggregate_type="material_receipt",
        aggregate_id=row_id,
        event_type="MaterialReceived",
        payload={
            "material_name": body.material_name.strip(),
            "quantity": str(body.quantity),
            "unit": body.unit.strip(),
            "occurred_date": body.occurred_date.isoformat(),
            "occurred_date_source": "reported",
        },
    )
    return {"id": row_id, "status": "success"}


@router.post("/outflows", status_code=201)
async def create_outflow(
    body: MaterialOutflowCreate,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Log a material usage/outflow directly from the mobile app."""
    # Verify project scope
    if not auth_context.project_scope.grants_all_org_projects:
        if body.project_id not in auth_context.project_scope.project_ids:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not authorized for this project")

    if _site_filter_denied(auth_context, body.project_id, body.site_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized for this site")

    from sqlalchemy import text

    row_id = uuid.uuid4()
    await conn.execute(
        text(
            "INSERT INTO material_usage "
            "(id, organization_id, project_id, site_id, material_name, quantity, unit, "
            "work_item, occurred_date, occurred_date_source, source, created_by) "
            "VALUES (:id, :organization_id, :project_id, :site_id, :material_name, "
            ":quantity, :unit, :work_item, :occurred_date, 'reported', 'mobile', :created_by)"
        ),
        {
            "id": row_id,
            "organization_id": auth_context.organization_id,
            "project_id": body.project_id,
            "site_id": body.site_id,
            "material_name": body.material_name.strip(),
            "quantity": body.quantity,
            "unit": body.unit.strip(),
            "work_item": body.work_item.strip() if body.work_item else None,
            "occurred_date": body.occurred_date,
            "created_by": auth_context.user_id,
        },
    )
    await _publish_outbox_event(
        conn,
        aggregate_type="material_usage",
        aggregate_id=row_id,
        event_type="MaterialUsed",
        payload={
            "material_name": body.material_name.strip(),
            "quantity": str(body.quantity),
            "unit": body.unit.strip(),
            "occurred_date": body.occurred_date.isoformat(),
            "occurred_date_source": "reported",
        },
    )
    return {"id": row_id, "status": "success"}

