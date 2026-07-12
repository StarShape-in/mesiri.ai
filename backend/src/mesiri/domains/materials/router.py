from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.authorization.context import AuthorizationContext
from mesiri.domains.materials.posting import post_material_movement
from mesiri.domains.materials.responses import (
    MaterialCatalogListResponse,
    MaterialCatalogResponse,
    MaterialLedgerResponse,
    MaterialReceiptResponse,
    MaterialReceiptsListResponse,
    MaterialStockResponse,
    MaterialUsageListResponse,
    MaterialUsageResponse,
)
from mesiri.domains.materials.validation import (
    ADJUSTMENT_REASONS,
    is_valid_receipt_reason,
    is_valid_usage_reason,
    role_can_adjust,
)
from mesiri.domains.projects.router import get_auth_context
from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.repositories.materials import (
    MaterialMovementsRepository,
    PostgresMaterialCatalogRepository,
    PostgresMaterialReadRepository,
    UnitsOfMeasureRepository,
)

router = APIRouter(prefix="/materials", tags=["materials"])


def _site_filter_denied(
    auth_context: AuthorizationContext,
    project_id: uuid.UUID | None,
    site_id: uuid.UUID | None,
) -> bool:
    """True if the requested site_id filter must be denied under the caller's site scope."""
    if site_id is None:
        return False
    if project_id is None:
        return not auth_context.project_scope.grants_all_org_projects
    site_scope = auth_context.site_scope_for_project(project_id)
    if site_scope.grants_all_sites:
        return False
    return site_id not in site_scope.site_ids


def _resolve_project_ids(
    auth_context: AuthorizationContext, project_id: uuid.UUID | None
) -> tuple[set[uuid.UUID] | None, bool]:
    """Returns (project_ids filter, denied). denied=True means caller has no access at all."""
    if project_id is not None:
        if not auth_context.project_scope.grants_all_org_projects:
            if project_id not in auth_context.project_scope.project_ids:
                return None, True
        return {project_id}, False
    if not auth_context.project_scope.grants_all_org_projects:
        if not auth_context.project_scope.project_ids:
            return None, True
        return auth_context.project_scope.project_ids, False
    return None, False


async def _publish_outbox_event(
    conn: AsyncConnection,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Write an outbox_events row on the caller's connection/transaction."""
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


async def _assert_site_in_project(
    conn: AsyncConnection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    site_id: uuid.UUID,
) -> None:
    row = (
        await conn.execute(
            text(
                "SELECT id FROM sites WHERE id = :site_id AND project_id = :project_id "
                "AND organization_id = :org_id"
            ),
            {"site_id": site_id, "project_id": project_id, "org_id": organization_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=422, detail="Site does not belong to the specified Project")


def _authorize_write(
    auth_context: AuthorizationContext, project_id: uuid.UUID, site_id: uuid.UUID | None
) -> None:
    if not auth_context.project_scope.grants_all_org_projects:
        if project_id not in auth_context.project_scope.project_ids:
            raise HTTPException(status_code=403, detail="Not authorized for this project")
    if _site_filter_denied(auth_context, project_id, site_id):
        raise HTTPException(status_code=403, detail="Not authorized for this site")


# ---------------------------------------------------------------------------
# Materials Catalog
# ---------------------------------------------------------------------------
class MaterialCatalogCreate(BaseModel):
    name: str
    default_unit_id: uuid.UUID
    category: str | None = None
    sku: str | None = None


class MaterialCatalogUpdate(BaseModel):
    name: str | None = None
    default_unit_id: uuid.UUID | None = None
    category: str | None = None
    sku: str | None = None
    is_active: bool | None = None


@router.get("", response_model=MaterialCatalogListResponse)
async def list_materials(
    search: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List Materials accessible to the caller's organization."""
    repo = PostgresMaterialCatalogRepository(conn)
    items, total = await repo.list_materials(
        organization_id=auth_context.organization_id,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/units-of-measure")
async def list_units_of_measure(
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List the fixed global units of measure — read-only, no per-org CRUD."""
    repo = UnitsOfMeasureRepository(conn)
    return {"items": await repo.list_active()}


@router.post("", response_model=MaterialCatalogResponse, status_code=201)
async def create_material(
    body: MaterialCatalogCreate,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Create a Material catalog entry (organization-scoped name) with its Stock Unit."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    units_repo = UnitsOfMeasureRepository(conn)
    unit = await units_repo.get_by_id(body.default_unit_id)
    if unit is None or not unit["is_active"]:
        raise HTTPException(status_code=422, detail="default_unit_id is not a valid active unit")

    repo = PostgresMaterialCatalogRepository(conn)
    existing = await repo.get_by_name(auth_context.organization_id, name)
    if existing is not None:
        raise HTTPException(status_code=409, detail="A Material with this name already exists")
    # Materials Catalog is org-scoped (no project_id/site_id), so it does not
    # fit the Timeline projector's per-project/site aggregate model — creation
    # is audited via the row's own created_at/created_by columns instead of
    # an outbox_events entry (see events/consumers/timeline_projector.py).
    return await repo.create(
        organization_id=auth_context.organization_id,
        name=name,
        default_unit=unit["code"],
        default_unit_id=unit["id"],
        category=body.category.strip() if body.category else None,
        sku=body.sku.strip() if body.sku else None,
        created_by=auth_context.user_id,
    )


@router.patch("/{material_id}", response_model=MaterialCatalogResponse)
async def update_material(
    material_id: uuid.UUID,
    body: MaterialCatalogUpdate,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Update a Material catalog entry. Stock Unit (default_unit_id) cannot change
    once any movement references this material — the unit a material is tracked
    in is fixed for its lifetime in V1 (no unit conversion)."""
    repo = PostgresMaterialCatalogRepository(conn)
    existing = await repo.get_by_id(auth_context.organization_id, material_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Material not found")

    default_unit_id = body.default_unit_id
    if default_unit_id is not None and default_unit_id != existing["default_unit_id"]:
        if await repo.has_movements(material_id):
            raise HTTPException(
                status_code=409,
                detail="Stock Unit cannot change: this material already has recorded movements",
            )
        units_repo = UnitsOfMeasureRepository(conn)
        unit = await units_repo.get_by_id(default_unit_id)
        if unit is None or not unit["is_active"]:
            raise HTTPException(status_code=422, detail="default_unit_id is not a valid active unit")

    name = body.name.strip() if body.name else None
    updated = await repo.update(
        auth_context.organization_id,
        material_id,
        name=name,
        default_unit_id=default_unit_id,
        category=body.category,
        sku=body.sku,
        is_active=body.is_active,
        updated_by=auth_context.user_id,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return updated


@router.delete("/{material_id}", status_code=204)
async def delete_material(
    material_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Delete an unused Material catalog entry.

    Materials with ledger history must be deactivated instead so inventory and
    audit history keep resolving to the original catalog row.
    """
    repo = PostgresMaterialCatalogRepository(conn)
    existing = await repo.get_by_id(auth_context.organization_id, material_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Material not found")
    deleted = await repo.delete_unused(auth_context.organization_id, material_id)
    if not deleted:
        raise HTTPException(
            status_code=409,
            detail="Material has recorded movements and cannot be deleted. Deactivate it instead.",
        )
    return None


# ---------------------------------------------------------------------------
# Inflows (material_receipts, direction=IN)
# ---------------------------------------------------------------------------
@router.get("/inflows", response_model=MaterialReceiptsListResponse)
async def list_inflows(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    material_id: uuid.UUID | None = None,
    material_name: str | None = None,
    movement_reason: str | None = None,
    source: str | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List material inflows (receipts) within the user's organization and project scope."""
    project_ids, denied = _resolve_project_ids(auth_context, project_id)
    if denied or _site_filter_denied(auth_context, project_id, site_id):
        return {"items": [], "total": 0}

    repo = PostgresMaterialReadRepository(conn)
    items, total = await repo.list_receipts(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
        material_id=material_id,
        material_name=material_name,
        movement_reason=movement_reason,
        source=source,
        recorded_by_user_id=recorded_by_user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/inflows/{receipt_id}", response_model=MaterialReceiptResponse)
async def get_inflow(
    receipt_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresMaterialReadRepository(conn)
    item = await repo.get_receipt(auth_context.organization_id, receipt_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inflow not found")
    if _site_filter_denied(auth_context, item["project_id"], item["site_id"]):
        raise HTTPException(status_code=403, detail="Not authorized for this movement")
    project_ids, denied = _resolve_project_ids(auth_context, item["project_id"])
    if denied:
        raise HTTPException(status_code=403, detail="Not authorized for this movement")
    return item


# ---------------------------------------------------------------------------
# Outflows (material_usage, direction=OUT)
# ---------------------------------------------------------------------------
@router.get("/outflows", response_model=MaterialUsageListResponse)
async def list_outflows(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    material_id: uuid.UUID | None = None,
    material_name: str | None = None,
    movement_reason: str | None = None,
    source: str | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List material outflows (usages) within the user's organization and project scope."""
    project_ids, denied = _resolve_project_ids(auth_context, project_id)
    if denied or _site_filter_denied(auth_context, project_id, site_id):
        return {"items": [], "total": 0}

    repo = PostgresMaterialReadRepository(conn)
    items, total = await repo.list_usage(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
        material_id=material_id,
        material_name=material_name,
        movement_reason=movement_reason,
        source=source,
        recorded_by_user_id=recorded_by_user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/outflows/{usage_id}", response_model=MaterialUsageResponse)
async def get_outflow(
    usage_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresMaterialReadRepository(conn)
    item = await repo.get_usage(auth_context.organization_id, usage_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Outflow not found")
    if _site_filter_denied(auth_context, item["project_id"], item["site_id"]):
        raise HTTPException(status_code=403, detail="Not authorized for this movement")
    project_ids, denied = _resolve_project_ids(auth_context, item["project_id"])
    if denied:
        raise HTTPException(status_code=403, detail="Not authorized for this movement")
    return item


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
@router.get("/inventory", response_model=list[MaterialStockResponse])
async def list_inventory(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    material_id: uuid.UUID | None = None,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Get aggregated material inventory (stock levels), derived from the movement ledger."""
    project_ids, denied = _resolve_project_ids(auth_context, project_id)
    if denied or _site_filter_denied(auth_context, project_id, site_id):
        return []

    repo = PostgresMaterialReadRepository(conn)
    return await repo.get_stock_levels(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
        material_id=material_id,
    )


@router.get("/ledger/{site_id}/{material_id}", response_model=MaterialLedgerResponse)
async def get_material_ledger(
    site_id: uuid.UUID,
    material_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Chronological movement history + running balance for one Site + Material."""
    site_row = (
        await conn.execute(
            text("SELECT project_id FROM sites WHERE id = :site_id AND organization_id = :org_id"),
            {"site_id": site_id, "org_id": auth_context.organization_id},
        )
    ).first()
    if site_row is None:
        raise HTTPException(status_code=404, detail="Site not found")
    project_id = site_row[0]
    if _site_filter_denied(auth_context, project_id, site_id):
        raise HTTPException(status_code=403, detail="Not authorized for this site")
    _, denied = _resolve_project_ids(auth_context, project_id)
    if denied:
        raise HTTPException(status_code=403, detail="Not authorized for this site")

    repo = PostgresMaterialReadRepository(conn)
    items, total = await repo.get_ledger(
        organization_id=auth_context.organization_id,
        site_id=site_id,
        material_id=material_id,
        limit=limit,
        offset=offset,
    )
    current_balance = items[0]["running_balance"] if items else None
    unit = items[0]["unit"] if items else None
    return {"items": items, "total": total, "current_balance": current_balance, "unit": unit}


# ---------------------------------------------------------------------------
# Write Schemas & Endpoints
# ---------------------------------------------------------------------------
class MaterialInflowCreate(BaseModel):
    project_id: uuid.UUID
    site_id: uuid.UUID | None = None
    material_id: uuid.UUID
    unit_id: uuid.UUID
    quantity: Decimal
    movement_reason: str = "RECEIVED"
    supplier: str | None = None
    notes: str | None = None
    occurred_date: datetime.date


class MaterialOutflowCreate(BaseModel):
    project_id: uuid.UUID
    site_id: uuid.UUID | None = None
    material_id: uuid.UUID
    unit_id: uuid.UUID
    quantity: Decimal
    movement_reason: str = "CONSUMED"
    work_item: str | None = None
    notes: str | None = None
    occurred_date: datetime.date


async def _resolve_and_validate_material_unit(
    conn: AsyncConnection,
    organization_id: uuid.UUID,
    material_id: uuid.UUID,
    unit_id: uuid.UUID,
) -> tuple[dict, dict]:
    """Look up the catalog material and unit by id and enforce the material's
    Stock Unit (materials_catalog.default_unit_id) — no free-text creation,
    no unit substitution. Raises HTTPException on any mismatch."""
    catalog_repo = PostgresMaterialCatalogRepository(conn)
    material = await catalog_repo.get_by_id(organization_id, material_id)
    if material is None or not material["is_active"]:
        raise HTTPException(status_code=422, detail="material_id is not a valid active catalog entry")

    units_repo = UnitsOfMeasureRepository(conn)
    unit = await units_repo.get_by_id(unit_id)
    if unit is None or not unit["is_active"]:
        raise HTTPException(status_code=422, detail="unit_id is not a valid active unit")

    if material["default_unit_id"] is not None and unit["id"] != material["default_unit_id"]:
        raise HTTPException(
            status_code=422,
            detail=(
                f"unit_id does not match {material['name']}'s Stock Unit "
                f"(expected {material['default_unit']}); no unit conversion is supported"
            ),
        )
    return material, unit


@router.post("/inflows", status_code=201)
async def create_inflow(
    body: MaterialInflowCreate,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Log a material receipt/inflow (web or mobile direct entry)."""
    if not is_valid_receipt_reason(body.movement_reason):
        raise HTTPException(
            status_code=422, detail=f"Invalid inflow movement_reason: {body.movement_reason}"
        )
    if body.movement_reason in ADJUSTMENT_REASONS and not role_can_adjust(auth_context.role):
        raise HTTPException(status_code=403, detail="Not authorized to record adjustment movements")
    if body.quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be greater than zero")

    _authorize_write(auth_context, body.project_id, body.site_id)
    if body.site_id is not None:
        await _assert_site_in_project(
            conn, auth_context.organization_id, body.project_id, body.site_id
        )

    material, unit = await _resolve_and_validate_material_unit(
        conn, auth_context.organization_id, body.material_id, body.unit_id
    )

    row_id = uuid.uuid4()
    await conn.execute(
        text(
            "INSERT INTO material_receipts "
            "(id, organization_id, project_id, site_id, material_name, quantity, unit, unit_id, "
            "supplier, occurred_date, occurred_date_source, source, movement_reason, notes, "
            "material_id, created_by) "
            "VALUES (:id, :organization_id, :project_id, :site_id, :material_name, "
            ":quantity, :unit, :unit_id, :supplier, :occurred_date, 'reported', 'web', "
            ":movement_reason, :notes, :material_id, :created_by)"
        ),
        {
            "id": row_id,
            "organization_id": auth_context.organization_id,
            "project_id": body.project_id,
            "site_id": body.site_id,
            "material_name": material["name"],
            "quantity": body.quantity,
            "unit": unit["code"],
            "unit_id": unit["id"],
            "supplier": body.supplier.strip() if body.supplier else None,
            "occurred_date": body.occurred_date,
            "movement_reason": body.movement_reason,
            "notes": body.notes.strip() if body.notes else None,
            "material_id": material["id"],
            "created_by": auth_context.user_id,
        },
    )
    await post_material_movement(
        conn,
        movement_type="RECEIPT",
        material_id=material["id"],
        unit_id=unit["id"],
        quantity=body.quantity,
        organization_id=auth_context.organization_id,
        project_id=body.project_id,
        site_id=body.site_id,
        occurred_at=datetime.datetime.combine(body.occurred_date, datetime.time.min),
        source_type="material_receipt",
        source_id=row_id,
        recorded_by_user_id=auth_context.user_id,
    )
    await _publish_outbox_event(
        conn,
        aggregate_type="material_receipt",
        aggregate_id=row_id,
        event_type="MaterialReceived",
        payload={
            "material_name": material["name"],
            "quantity": str(body.quantity),
            "unit": unit["code"],
            "movement_reason": body.movement_reason,
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
    """Log a material usage/outflow (web or mobile direct entry)."""
    if not is_valid_usage_reason(body.movement_reason):
        raise HTTPException(
            status_code=422, detail=f"Invalid outflow movement_reason: {body.movement_reason}"
        )
    if body.movement_reason in ADJUSTMENT_REASONS and not role_can_adjust(auth_context.role):
        raise HTTPException(status_code=403, detail="Not authorized to record adjustment movements")
    if body.quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be greater than zero")

    _authorize_write(auth_context, body.project_id, body.site_id)
    if body.site_id is not None:
        await _assert_site_in_project(
            conn, auth_context.organization_id, body.project_id, body.site_id
        )

    material, unit = await _resolve_and_validate_material_unit(
        conn, auth_context.organization_id, body.material_id, body.unit_id
    )

    row_id = uuid.uuid4()
    await conn.execute(
        text(
            "INSERT INTO material_usage "
            "(id, organization_id, project_id, site_id, material_name, quantity, unit, unit_id, "
            "work_item, occurred_date, occurred_date_source, source, movement_reason, notes, "
            "material_id, created_by) "
            "VALUES (:id, :organization_id, :project_id, :site_id, :material_name, "
            ":quantity, :unit, :unit_id, :work_item, :occurred_date, 'reported', 'web', "
            ":movement_reason, :notes, :material_id, :created_by)"
        ),
        {
            "id": row_id,
            "organization_id": auth_context.organization_id,
            "project_id": body.project_id,
            "site_id": body.site_id,
            "material_name": material["name"],
            "quantity": body.quantity,
            "unit": unit["code"],
            "unit_id": unit["id"],
            "work_item": body.work_item.strip() if body.work_item else None,
            "occurred_date": body.occurred_date,
            "movement_reason": body.movement_reason,
            "notes": body.notes.strip() if body.notes else None,
            "material_id": material["id"],
            "created_by": auth_context.user_id,
        },
    )
    await post_material_movement(
        conn,
        movement_type="ISSUE",
        material_id=material["id"],
        unit_id=unit["id"],
        quantity=body.quantity,
        organization_id=auth_context.organization_id,
        project_id=body.project_id,
        site_id=body.site_id,
        occurred_at=datetime.datetime.combine(body.occurred_date, datetime.time.min),
        source_type="material_usage",
        source_id=row_id,
        recorded_by_user_id=auth_context.user_id,
    )
    await _publish_outbox_event(
        conn,
        aggregate_type="material_usage",
        aggregate_id=row_id,
        event_type="MaterialUsed",
        payload={
            "material_name": material["name"],
            "quantity": str(body.quantity),
            "unit": unit["code"],
            "movement_reason": body.movement_reason,
            "occurred_date": body.occurred_date.isoformat(),
            "occurred_date_source": "reported",
        },
    )
    return {"id": row_id, "status": "success"}


# ---------------------------------------------------------------------------
# Corrections / Reversals
# ---------------------------------------------------------------------------
class MaterialReversalCreate(BaseModel):
    reason_note: str | None = None
    occurred_date: datetime.date | None = None


@router.post("/inflows/{receipt_id}/reverse", status_code=201)
async def reverse_inflow(
    receipt_id: uuid.UUID,
    body: MaterialReversalCreate,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Correct a confirmed Inflow by recording an offsetting ADJUSTMENT_OUT outflow.

    The original movement is never edited or deleted; this inserts a new
    outflow row referencing it via reverses_movement_id, preserving history.
    """
    if not role_can_adjust(auth_context.role):
        raise HTTPException(status_code=403, detail="Not authorized to correct movements")

    repo = PostgresMaterialReadRepository(conn)
    original = await repo.get_receipt(auth_context.organization_id, receipt_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Inflow not found")
    _authorize_write(auth_context, original["project_id"], original["site_id"])

    row_id = uuid.uuid4()
    occurred_date = body.occurred_date or datetime.date.today()
    await conn.execute(
        text(
            "INSERT INTO material_usage "
            "(id, organization_id, project_id, site_id, material_name, quantity, unit, unit_id, "
            "work_item, occurred_date, occurred_date_source, source, movement_reason, notes, "
            "material_id, reverses_movement_id, created_by) "
            "VALUES (:id, :organization_id, :project_id, :site_id, :material_name, "
            ":quantity, :unit, :unit_id, NULL, :occurred_date, 'reported', 'web', "
            "'ADJUSTMENT_OUT', :notes, :material_id, :reverses_movement_id, :created_by)"
        ),
        {
            "id": row_id,
            "organization_id": auth_context.organization_id,
            "project_id": original["project_id"],
            "site_id": original["site_id"],
            "material_name": original["material_name"],
            "quantity": original["quantity"],
            "unit": original["unit"],
            "unit_id": original["unit_id"],
            "occurred_date": occurred_date,
            "notes": body.reason_note,
            "material_id": original["material_id"],
            "reverses_movement_id": receipt_id,
            "created_by": auth_context.user_id,
        },
    )
    movements_repo = MaterialMovementsRepository(conn)
    original_movement = await movements_repo.get_by_source("material_receipt", receipt_id)
    await post_material_movement(
        conn,
        movement_type="ISSUE",
        material_id=original["material_id"],
        unit_id=original["unit_id"],
        quantity=original["quantity"],
        organization_id=auth_context.organization_id,
        project_id=original["project_id"],
        site_id=original["site_id"],
        occurred_at=datetime.datetime.combine(occurred_date, datetime.time.min),
        source_type="material_usage",
        source_id=row_id,
        recorded_by_user_id=auth_context.user_id,
        reversal_of_movement_id=original_movement["id"] if original_movement else None,
    )
    await _publish_outbox_event(
        conn,
        aggregate_type="material_usage",
        aggregate_id=row_id,
        event_type="MaterialMovementCorrected",
        payload={"reverses_movement_id": str(receipt_id), "movement_reason": "ADJUSTMENT_OUT"},
    )
    return {"id": row_id, "status": "success"}


@router.post("/outflows/{usage_id}/reverse", status_code=201)
async def reverse_outflow(
    usage_id: uuid.UUID,
    body: MaterialReversalCreate,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Correct a confirmed Outflow by recording an offsetting ADJUSTMENT_IN inflow."""
    if not role_can_adjust(auth_context.role):
        raise HTTPException(status_code=403, detail="Not authorized to correct movements")

    repo = PostgresMaterialReadRepository(conn)
    original = await repo.get_usage(auth_context.organization_id, usage_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Outflow not found")
    _authorize_write(auth_context, original["project_id"], original["site_id"])

    row_id = uuid.uuid4()
    occurred_date = body.occurred_date or datetime.date.today()
    await conn.execute(
        text(
            "INSERT INTO material_receipts "
            "(id, organization_id, project_id, site_id, material_name, quantity, unit, unit_id, "
            "supplier, occurred_date, occurred_date_source, source, movement_reason, notes, "
            "material_id, reverses_movement_id, created_by) "
            "VALUES (:id, :organization_id, :project_id, :site_id, :material_name, "
            ":quantity, :unit, :unit_id, NULL, :occurred_date, 'reported', 'web', "
            "'ADJUSTMENT_IN', :notes, :material_id, :reverses_movement_id, :created_by)"
        ),
        {
            "id": row_id,
            "organization_id": auth_context.organization_id,
            "project_id": original["project_id"],
            "site_id": original["site_id"],
            "material_name": original["material_name"],
            "quantity": original["quantity"],
            "unit": original["unit"],
            "unit_id": original["unit_id"],
            "occurred_date": occurred_date,
            "notes": body.reason_note,
            "material_id": original["material_id"],
            "reverses_movement_id": usage_id,
            "created_by": auth_context.user_id,
        },
    )
    movements_repo = MaterialMovementsRepository(conn)
    original_movement = await movements_repo.get_by_source("material_usage", usage_id)
    await post_material_movement(
        conn,
        movement_type="RECEIPT",
        material_id=original["material_id"],
        unit_id=original["unit_id"],
        quantity=original["quantity"],
        organization_id=auth_context.organization_id,
        project_id=original["project_id"],
        site_id=original["site_id"],
        occurred_at=datetime.datetime.combine(occurred_date, datetime.time.min),
        source_type="material_receipt",
        source_id=row_id,
        recorded_by_user_id=auth_context.user_id,
        reversal_of_movement_id=original_movement["id"] if original_movement else None,
    )
    await _publish_outbox_event(
        conn,
        aggregate_type="material_receipt",
        aggregate_id=row_id,
        event_type="MaterialMovementCorrected",
        payload={"reverses_movement_id": str(usage_id), "movement_reason": "ADJUSTMENT_IN"},
    )
    return {"id": row_id, "status": "success"}
