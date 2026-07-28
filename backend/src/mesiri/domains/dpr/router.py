"""REST API for Daily Progress Reports (DPR).

Mounted at /dpr so:
  GET   /dpr/daily-reports                 list daily reports
  GET   /dpr/daily-reports/{report_id}     get daily report details
  POST  /dpr/daily-reports                 create daily report draft
  POST  /dpr/daily-reports/{report_id}/approve approve a report
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.authorization.context import AuthorizationContext
from mesiri.domains.projects.router import get_auth_context
from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.repositories.dpr import PostgresDprRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dpr", tags=["dpr"])


class CreateDprRequest(BaseModel):
    report_date: str
    project_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None
    weather: str = "sunny"
    temperature_celsius: float | None = None
    shift: str = "day"
    narrative_summary: str | None = None
    work_items: list[dict[str, Any]] = []
    labour_items: list[dict[str, Any]] = []
    equipment_items: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []


class ApproveDprRequest(BaseModel):
    notes: str | None = None


def _resolve_project_ids(
    auth_context: AuthorizationContext, project_id: uuid.UUID | None
) -> tuple[set[uuid.UUID] | None, bool]:
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


@router.get("/daily-reports")
async def list_daily_reports(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    status: str | None = None,
    category: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    project_ids, denied = _resolve_project_ids(auth_context, project_id)
    if denied:
        return {"items": [], "total": 0}

    repo = PostgresDprRepository(conn)
    items, total = await repo.list_reports(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/daily-reports/{report_id}")
async def get_daily_report_detail(
    report_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresDprRepository(conn)
    report = await repo.get_report(
        organization_id=auth_context.organization_id,
        report_id=report_id,
    )
    if not report:
        raise HTTPException(status_code=404, detail="Daily report not found")
    return report


@router.post("/daily-reports")
async def create_daily_report(
    req: CreateDprRequest,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresDprRepository(conn)
    created = await repo.create_report(
        organization_id=auth_context.organization_id,
        user_id=auth_context.user_id,
        payload=req.model_dump(),
    )
    return created


@router.post("/daily-reports/{report_id}/submit-for-review")
async def submit_daily_report_for_review(
    report_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """DRAFT -> IN_REVIEW."""
    repo = PostgresDprRepository(conn)
    success = await repo.submit_for_review(
        organization_id=auth_context.organization_id,
        report_id=report_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Report not found or not in DRAFT status")
    return {"status": "success"}


@router.post("/daily-reports/{report_id}/approve")
async def approve_daily_report(
    report_id: uuid.UUID,
    req: ApproveDprRequest,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresDprRepository(conn)
    success = await repo.approve_report(
        organization_id=auth_context.organization_id,
        user_id=auth_context.user_id,
        report_id=report_id,
        notes=req.notes,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Report not found or already approved")
    return {"status": "success"}


@router.post("/daily-reports/{report_id}/publish")
async def publish_daily_report(
    report_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """APPROVED -> PUBLISHED."""
    repo = PostgresDprRepository(conn)
    success = await repo.publish_report(
        organization_id=auth_context.organization_id,
        report_id=report_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Report not found or not in APPROVED status")
    return {"status": "success"}
