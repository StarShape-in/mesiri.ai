"""Projects domain router — org-scoped project and site management.

Endpoints
---------
GET  /projects                     list projects accessible to the caller
POST /projects                     create a new project  (admin / PM)
GET  /projects/{id}/sites          list sites for a project
POST /projects/{id}/sites          create a site  (admin / PM)

Architecture
------------
GET /projects flow:
HTTP Router → ListProjects Query → Handler → AuthorizationContext →
Project Repository → PostgreSQL → DTO → Presenter → Response
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from ...application.projects.handlers import ListProjectsHandler
from ...application.projects.queries import ListProjects
from ...authorization.context import AuthorizationContext
from ...authorization.service import AuthorizationService
from ...infrastructure.postgres.dependency import get_db_conn
from ...infrastructure.postgres.repositories.projects import PostgresProjectRepository
from ..shared.auth import get_current_user, require_admin
from .presenter import ProjectPresenter
from .responses import ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])

# ---------------------------------------------------------------------------
# Legacy table definitions (used by non-refactored endpoints)
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
# Legacy schema definitions (used by non-refactored endpoints)
# ---------------------------------------------------------------------------


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
# Dependencies
# ---------------------------------------------------------------------------


async def get_auth_context(
    jwt_payload: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db_conn),
) -> AuthorizationContext:
    """Resolve authorization context for the current request.
    
    Validates JWT, loads current user from database, verifies status,
    and resolves project access scope.
    """
    user_id = uuid.UUID(jwt_payload["sub"])
    org_id = uuid.UUID(jwt_payload["org"])
    role = jwt_payload.get("role", "user")
    
    auth_service = AuthorizationService(conn)
    return await auth_service.resolve_from_jwt(user_id, org_id, role)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List all projects accessible to the authenticated user.
    
    Returns projects according to the user's access policy:
    - all_projects mode: all projects in user's organization
    - custom_projects mode: only explicitly granted projects
    - Empty custom scope: returns empty list
    
    Projects are ordered by name (ascending).
    Status values are mapped from database (on_track, at_risk, critical)
    to external API (success, warning, critical).
    """
    # Create repository and handler
    repository = PostgresProjectRepository(conn)
    handler = ListProjectsHandler(repository)
    
    # Execute query
    query = ListProjects()
    projects = await handler.handle(query, auth_context)
    
    # Transform to HTTP response
    return ProjectPresenter.to_response_list(projects)


# ---------------------------------------------------------------------------
# Legacy routes (not refactored in this vertical slice)
# ---------------------------------------------------------------------------


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
