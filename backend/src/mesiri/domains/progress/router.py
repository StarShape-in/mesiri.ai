"""REST API for the Progress (Daily Reporting) module — read-only in V1.

Mounted at /progress so:
  GET   /progress/activities                list activities
  GET   /progress/activities/{activity_id}    one activity with quantities/
                                              progress updates/attachments

Activities and Progress Updates are never written here. Per plan principle
P2 (the universal operational pattern — nothing persisted before an explicit
confirmation) they are always WhatsApp-confirmed, owned by
application/progress/* + progress_execution.py, the same split Labour draws
between PostgresWorkforceReadRepository and labour_execution.py. This router
only reads.
"""

from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.authorization.context import AuthorizationContext
from mesiri.domains.projects.router import get_auth_context
from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.repositories.progress import PostgresProgressReadRepository

from .responses import (
    ActivitiesListResponse,
    ActivityDetailResponse,
    CreateSiteIssueRequest,
    ResolveSiteIssueRequest,
    SiteIssueResponse,
    SiteIssuesListResponse,
)

router = APIRouter(prefix="/progress", tags=["progress"])



def _resolve_project_ids(
    auth_context: AuthorizationContext, project_id: uuid.UUID | None
) -> tuple[set[uuid.UUID] | None, bool]:
    """Returns (project_ids filter, denied). denied=True means caller has no
    access at all. Identical to materials/router.py and workforce/router.py's
    helper of the same name."""
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


def _site_filter_denied(
    auth_context: AuthorizationContext,
    project_id: uuid.UUID | None,
    site_id: uuid.UUID | None,
) -> bool:
    if site_id is None:
        return False
    if project_id is None:
        return not auth_context.project_scope.grants_all_org_projects
    site_scope = auth_context.site_scope_for_project(project_id)
    if site_scope.grants_all_sites:
        return False
    return site_id not in site_scope.site_ids


@router.get("/activities", response_model=ActivitiesListResponse)
async def list_activities(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    status: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List activities within the caller's organization and project scope."""
    project_ids, denied = _resolve_project_ids(auth_context, project_id)
    if denied or _site_filter_denied(auth_context, project_id, site_id):
        return {"items": [], "total": 0}

    repo = PostgresProgressReadRepository(conn)
    items, total = await repo.list_activities(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/activities/{activity_id}", response_model=ActivityDetailResponse)
async def get_activity(
    activity_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresProgressReadRepository(conn)
    item = await repo.get_activity(auth_context.organization_id, activity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    if _site_filter_denied(auth_context, item["project_id"], item["site_id"]):
        raise HTTPException(status_code=403, detail="Not authorized for this activity")
    _project_ids, denied = _resolve_project_ids(auth_context, item["project_id"])
    if denied:
        raise HTTPException(status_code=403, detail="Not authorized for this activity")

    return item


@router.get("/issues", response_model=SiteIssuesListResponse)
async def list_issues(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List site issues within the caller's organization and project scope."""
    project_ids, denied = _resolve_project_ids(auth_context, project_id)
    if denied or _site_filter_denied(auth_context, project_id, site_id):
        return {"items": [], "total": 0}

    repo = PostgresProgressReadRepository(conn)
    items, total = await repo.list_issues(
        organization_id=auth_context.organization_id,
        project_ids=project_ids,
        site_id=site_id,
        status=status,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/issues/{issue_id}", response_model=SiteIssueResponse)
async def get_issue(
    issue_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresProgressReadRepository(conn)
    item = await repo.get_issue(auth_context.organization_id, issue_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    if _site_filter_denied(auth_context, item["project_id"], item["site_id"]):
        raise HTTPException(status_code=403, detail="Not authorized for this issue")
    _project_ids, denied = _resolve_project_ids(auth_context, item["project_id"])
    if denied:
        raise HTTPException(status_code=403, detail="Not authorized for this issue")

    return item


@router.post("/issues", response_model=SiteIssueResponse, status_code=201)
async def create_issue(
    payload: CreateSiteIssueRequest,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Create a new site issue / blocker."""
    _project_ids, denied = _resolve_project_ids(auth_context, payload.project_id)
    if denied or _site_filter_denied(auth_context, payload.project_id, payload.site_id):
        raise HTTPException(status_code=403, detail="Not authorized for target project or site")

    repo = PostgresProgressReadRepository(conn)
    item = await repo.create_issue(
        organization_id=auth_context.organization_id,
        user_id=auth_context.user_id,
        payload=payload.model_dump(),
    )
    return item


@router.post("/issues/{issue_id}/resolve")
async def resolve_issue(
    issue_id: uuid.UUID,
    payload: ResolveSiteIssueRequest,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Mark a site issue as RESOLVED with resolution notes."""
    repo = PostgresProgressReadRepository(conn)
    existing = await repo.get_issue(auth_context.organization_id, issue_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    if _site_filter_denied(auth_context, existing["project_id"], existing["site_id"]):
        raise HTTPException(status_code=403, detail="Not authorized for this issue")

    success = await repo.resolve_issue(
        organization_id=auth_context.organization_id,
        issue_id=issue_id,
        notes=payload.resolution_notes,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Issue is already resolved or cannot be updated")

    return {"status": "success", "message": "Site issue resolved"}

