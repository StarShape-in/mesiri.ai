"""Projects router — live, tenant-scoped project management for the Mesiri app.

Reads/writes the control-plane ``projects`` table, scoped to the caller's
organization (the JWT ``org`` claim). Mirrors the users router's standalone
engine + JWT auth pattern so the mobile app has a real backend instead of mock
data.
"""

from __future__ import annotations

import os
import uuid

import jwt
import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine

from context.projection_hooks import project_entity

router = APIRouter(prefix="/projects", tags=["projects"])

SECRET_KEY = "mesiri-temp-secret-key-change-in-production"
ALGORITHM = "HS256"

# Roles allowed to create projects.
_CREATE_ROLES = {"ADMIN", "PROJECT_MANAGER"}
_VALID_STATUS = {"on_track", "at_risk", "critical"}

# status -> (StatusType for the UI badge, human label)
_STATUS_DISPLAY = {
    "on_track": ("success", "On Track"),
    "at_risk": ("warning", "At Risk"),
    "critical": ("critical", "Critical"),
}


def _get_engine():
    host = os.environ.get("MESIRI_POSTGRES__HOST", "localhost")
    port = os.environ.get("MESIRI_POSTGRES__PORT", "5432")
    user = os.environ.get("MESIRI_POSTGRES__USER", "mesiri")
    password = os.environ.get("MESIRI_POSTGRES__PASSWORD", "mesiri_local_dev")
    database = os.environ.get("MESIRI_POSTGRES__DATABASE", "mesiri")
    dsn = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return create_async_engine(dsn, echo=False, pool_pre_ping=True)


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine


projects_table = sa.Table(
    "projects",
    sa.MetaData(),
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("organization_id", sa.UUID),
    sa.Column("name", sa.String),
    sa.Column("code", sa.String),
    sa.Column("location", sa.String),
    sa.Column("client", sa.String),
    sa.Column("description", sa.String),
    sa.Column("status", sa.String),
    sa.Column("progress", sa.Integer),
    sa.Column("open_issues", sa.Integer),
)

sites_table = sa.Table(
    "sites",
    sa.MetaData(),
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("project_id", sa.UUID),
    sa.Column("organization_id", sa.UUID),
    sa.Column("name", sa.String),
    sa.Column("status", sa.String),
)

project_members_table = sa.Table(
    "project_members",
    sa.MetaData(),
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("project_id", sa.UUID),
    sa.Column("user_id", sa.UUID),
    sa.Column("role", sa.String),
)

# Minimal shim -- only the columns this router needs (email/full_name/status
# for rendering a member row, organization_id to scope user lookups). See
# users/router.py for the fuller shim used by user-management endpoints.
users_table = sa.Table(
    "users",
    sa.MetaData(),
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("organization_id", sa.UUID),
    sa.Column("email", sa.String),
    sa.Column("full_name", sa.String),
    sa.Column("status", sa.String),
)


# ---------------------------------------------------------------------------
# Schemas — shaped for the mobile ProjectHealthCard.
# ---------------------------------------------------------------------------
class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    location: str | None = None
    code: str | None = None
    client: str | None = None
    description: str | None = None
    status: str  # StatusType: success | warning | critical
    statusLabel: str
    progress: int
    openIssues: int
    reportingRatio: str | None = None


class ProjectCreate(BaseModel):
    name: str
    location: str | None = None
    code: str | None = None
    client: str | None = None
    description: str | None = None
    status: str = "on_track"
    progress: int = 0


class SiteResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    status: str


class SiteCreate(BaseModel):
    name: str
    status: str = "active"


class ProjectMemberResponse(BaseModel):
    userId: uuid.UUID
    email: str
    fullName: str
    role: str
    status: str


class ProjectMemberAdd(BaseModel):
    userId: uuid.UUID
    role: str = "SITE_ENGINEER"


def _to_response(row) -> ProjectResponse:
    status = row.status if row.status in _VALID_STATUS else "on_track"
    ui_status, label = _STATUS_DISPLAY[status]
    return ProjectResponse(
        id=row.id,
        name=row.name,
        location=row.location,
        code=row.code,
        client=row.client,
        description=row.description,
        status=ui_status,
        statusLabel=label,
        progress=row.progress or 0,
        openIssues=row.open_issues or 0,
        reportingRatio=None,  # no sites/reporting subsystem yet
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _decode(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    try:
        return jwt.decode(authorization.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


async def get_current_user(authorization: str = Header(None)) -> dict:
    return _decode(authorization)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=list[ProjectResponse])
async def list_projects(payload: dict = Depends(get_current_user)):
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(projects_table)
            .where(projects_table.c.organization_id == org_id)
            .order_by(projects_table.c.name)
        )
        rows = result.fetchall()
    return [_to_response(r) for r in rows]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, payload: dict = Depends(get_current_user)):
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(projects_table).where(
                projects_table.c.id == project_id,
                projects_table.c.organization_id == org_id,
            )
        )
        row = result.first()

    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_response(row)


@router.get("/{project_id}/sites", response_model=list[SiteResponse])
async def list_project_sites(project_id: uuid.UUID, payload: dict = Depends(get_current_user)):
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    engine = get_engine()
    async with engine.connect() as conn:
        project_result = await conn.execute(
            sa.select(projects_table.c.id).where(
                projects_table.c.id == project_id,
                projects_table.c.organization_id == org_id,
            )
        )
        if project_result.first() is None:
            raise HTTPException(status_code=404, detail="Project not found")

        result = await conn.execute(
            sa.select(sites_table)
            .where(
                sites_table.c.project_id == project_id,
                sites_table.c.organization_id == org_id,
            )
            .order_by(sites_table.c.name)
        )
        rows = result.fetchall()

    return [
        SiteResponse(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            status=row.status or "active",
        )
        for row in rows
    ]


@router.post("/{project_id}/sites", response_model=SiteResponse)
async def create_project_site(
    project_id: uuid.UUID,
    site_in: SiteCreate,
    payload: dict = Depends(get_current_user),
):
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    if (payload.get("role") or "").upper() not in _CREATE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to create sites")

    name = site_in.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Site name is required")

    engine = get_engine()
    async with engine.begin() as conn:
        project_result = await conn.execute(
            sa.select(projects_table.c.id).where(
                projects_table.c.id == project_id,
                projects_table.c.organization_id == org_id,
            )
        )
        if project_result.first() is None:
            raise HTTPException(status_code=404, detail="Project not found")

        site_id = uuid.uuid4()
        status = site_in.status.strip() or "active"
        await conn.execute(
            sites_table.insert().values(
                id=site_id,
                project_id=project_id,
                organization_id=org_id,
                name=name,
                status=status,
            )
        )

    await project_entity("site", site_id)
    return SiteResponse(id=site_id, project_id=project_id, name=name, status=status)


@router.post("", response_model=ProjectResponse)
async def create_project(project_in: ProjectCreate, payload: dict = Depends(get_current_user)):
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    if (payload.get("role") or "").upper() not in _CREATE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to create projects")
    if not project_in.name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    status = project_in.status if project_in.status in _VALID_STATUS else "on_track"
    progress = max(0, min(100, project_in.progress))
    project_id = uuid.uuid4()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            projects_table.insert().values(
                id=project_id,
                organization_id=org_id,
                name=project_in.name.strip(),
                code=project_in.code,
                location=project_in.location,
                client=project_in.client,
                description=project_in.description,
                status=status,
                progress=progress,
                open_issues=0,
            )
        )

    await project_entity("project", project_id)

    ui_status, label = _STATUS_DISPLAY[status]
    return ProjectResponse(
        id=project_id,
        name=project_in.name.strip(),
        location=project_in.location,
        code=project_in.code,
        client=project_in.client,
        description=project_in.description,
        status=ui_status,
        statusLabel=label,
        progress=progress,
        openIssues=0,
        reportingRatio=None,
    )


# ---------------------------------------------------------------------------
# Project members -- the source of truth AuthorizationService and the
# WhatsApp context resolver both now read (see project/site membership audit
# and context/identity_projection.py's _project_membership). These endpoints
# were previously only defined in backend/src/mesiri/domains/projects/router
# .py, a router that is never mounted by the app actually deployed in
# production (this one) -- the dashboard's Project Members tab has been
# calling a 404 the whole time. Same URL paths and response shape as that
# router's ProjectMemberResponse/ProjectMemberAdd, so the dashboard needs no
# changes.
# ---------------------------------------------------------------------------
def _to_member_response(row) -> ProjectMemberResponse:
    return ProjectMemberResponse(
        userId=row.user_id,
        email=row.email,
        fullName=row.full_name,
        role=row.role,
        status=row.status,
    )


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_project_members(project_id: uuid.UUID, payload: dict = Depends(get_current_user)):
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    engine = get_engine()
    async with engine.connect() as conn:
        project_result = await conn.execute(
            sa.select(projects_table.c.id).where(
                projects_table.c.id == project_id,
                projects_table.c.organization_id == org_id,
            )
        )
        if project_result.first() is None:
            raise HTTPException(status_code=404, detail="Project not found")

        result = await conn.execute(
            sa.select(
                project_members_table.c.user_id,
                project_members_table.c.role,
                users_table.c.email,
                users_table.c.full_name,
                users_table.c.status,
            )
            .select_from(
                project_members_table.join(
                    users_table, users_table.c.id == project_members_table.c.user_id
                )
            )
            .where(project_members_table.c.project_id == project_id)
        )
        rows = result.fetchall()

    return [_to_member_response(r) for r in rows]


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=201)
async def add_project_member(
    project_id: uuid.UUID,
    body: ProjectMemberAdd,
    payload: dict = Depends(get_current_user),
):
    if (payload.get("role") or "").upper() != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required to add member")
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    engine = get_engine()
    async with engine.begin() as conn:
        project_result = await conn.execute(
            sa.select(projects_table.c.id).where(
                projects_table.c.id == project_id,
                projects_table.c.organization_id == org_id,
            )
        )
        if project_result.first() is None:
            raise HTTPException(status_code=404, detail="Project not found")

        user_result = await conn.execute(
            sa.select(users_table).where(
                users_table.c.id == body.userId,
                users_table.c.organization_id == org_id,
            )
        )
        user_row = user_result.first()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found in organization")

        try:
            await conn.execute(
                project_members_table.insert().values(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    user_id=body.userId,
                    role=body.role,
                )
            )
        except Exception as exc:
            if "unique" in str(exc).lower() or "23505" in str(exc):
                raise HTTPException(
                    status_code=409, detail="User is already a member of this project"
                ) from exc
            raise

    await project_entity("membership", body.userId)
    return ProjectMemberResponse(
        userId=user_row.id,
        email=user_row.email,
        fullName=user_row.full_name,
        role=body.role,
        status=user_row.status,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict = Depends(get_current_user),
):
    if (payload.get("role") or "").upper() != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required to remove member")
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    engine = get_engine()
    async with engine.begin() as conn:
        project_result = await conn.execute(
            sa.select(projects_table.c.id).where(
                projects_table.c.id == project_id,
                projects_table.c.organization_id == org_id,
            )
        )
        if project_result.first() is None:
            raise HTTPException(status_code=404, detail="Project not found")

        await conn.execute(
            project_members_table.delete().where(
                project_members_table.c.project_id == project_id,
                project_members_table.c.user_id == user_id,
            )
        )

    await project_entity("membership", user_id)
