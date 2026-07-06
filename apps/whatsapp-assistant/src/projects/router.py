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
    status: str            # StatusType: success | warning | critical
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


@router.post("", response_model=ProjectResponse)
async def create_project(project_in: ProjectCreate, payload: dict = Depends(get_current_user)):
    org_id = payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    if payload.get("role") not in _CREATE_ROLES:
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
