"""Projects domain router — org-scoped project and site management.

Endpoints
---------
GET  /projects                     list projects in the caller's org
POST /projects                     create a new project  (admin / PM)
GET  /projects/{id}/sites          list sites for a project
POST /projects/{id}/sites          create a site  (admin / PM)
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from ...infrastructure.postgres.dependency import get_db_conn
from ..shared.auth import get_current_user, require_admin

router = APIRouter(prefix="/projects", tags=["projects"])

# ---------------------------------------------------------------------------
# Raw table refs
# ---------------------------------------------------------------------------
_projects = sa.Table(
    "projects",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("name", sa.String),
    sa.Column("code", sa.String),
    sa.Column("location", sa.String),
    sa.Column("client", sa.String),
    sa.Column("description", sa.String),
    sa.Column("status", sa.String),
    sa.Column("progress", sa.Integer),
    sa.Column("open_issues", sa.Integer),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_sites = sa.Table(
    "sites",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("name", sa.String),
    sa.Column("status", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None = None
    location: str | None = None
    client: str | None = None
    description: str | None = None
    status: str
    progress: int
    open_issues: int


class ProjectCreate(BaseModel):
    name: str
    code: str | None = None
    location: str | None = None
    client: str | None = None
    description: str | None = None


class SiteResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    status: str


class SiteCreate(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db_conn),
):
    org_id = user.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="Token missing org claim")

    result = await conn.execute(
        sa.select(_projects).where(_projects.c.organization_id == org_id)
    )
    return [
        ProjectResponse(
            id=r.id,
            name=r.name,
            code=r.code,
            location=r.location,
            client=r.client,
            description=r.description,
            status=r.status or "on_track",
            progress=r.progress or 0,
            open_issues=r.open_issues or 0,
        )
        for r in result.fetchall()
    ]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    admin: dict = Depends(require_admin),
    conn: AsyncConnection = Depends(get_db_conn),
):
    org_id = admin.get("org")
    project_id = uuid.uuid4()
    await conn.execute(
        _projects.insert().values(
            id=project_id,
            organization_id=org_id,
            name=body.name,
            code=body.code,
            location=body.location,
            client=body.client,
            description=body.description,
        )
    )
    return ProjectResponse(
        id=project_id,
        name=body.name,
        code=body.code,
        location=body.location,
        client=body.client,
        description=body.description,
        status="on_track",
        progress=0,
        open_issues=0,
    )


@router.get("/{project_id}/sites", response_model=list[SiteResponse])
async def list_sites(
    project_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db_conn),
):
    org_id = user.get("org")

    proj_result = await conn.execute(
        sa.select(_projects.c.id).where(
            _projects.c.id == project_id,
            _projects.c.organization_id == org_id,
        )
    )
    if proj_result.first() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await conn.execute(
        sa.select(_sites).where(_sites.c.project_id == project_id)
    )
    return [
        SiteResponse(
            id=r.id,
            project_id=r.project_id,
            name=r.name,
            status=r.status or "active",
        )
        for r in result.fetchall()
    ]


@router.post("/{project_id}/sites", response_model=SiteResponse, status_code=201)
async def create_site(
    project_id: uuid.UUID,
    body: SiteCreate,
    admin: dict = Depends(require_admin),
    conn: AsyncConnection = Depends(get_db_conn),
):
    org_id = admin.get("org")

    proj_result = await conn.execute(
        sa.select(_projects.c.id).where(
            _projects.c.id == project_id,
            _projects.c.organization_id == org_id,
        )
    )
    if proj_result.first() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    site_id = uuid.uuid4()
    await conn.execute(
        _sites.insert().values(
            id=site_id,
            project_id=project_id,
            organization_id=org_id,
            name=body.name,
        )
    )
    return SiteResponse(
        id=site_id,
        project_id=project_id,
        name=body.name,
        status="active",
    )
