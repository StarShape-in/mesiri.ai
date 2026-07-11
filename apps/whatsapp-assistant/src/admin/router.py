"""Admin router for Control Plane - tenant provisioning."""

from __future__ import annotations

import os
import uuid
from datetime import datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine

from context.projection_hooks import project_entity
from mesiri.domains.shared.auth import require_platform_admin

router = APIRouter(prefix="/admin/organizations", tags=["admin"])


# ---------------------------------------------------------------------------
# DB Connection (standalone for the admin router)
# ---------------------------------------------------------------------------
def _get_engine():
    """Build async engine from environment variables."""
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


# ---------------------------------------------------------------------------
# Tables (raw SQLAlchemy core - no ORM needed)
# ---------------------------------------------------------------------------
metadata = sa.MetaData()

organizations_table = sa.Table(
    "organizations",
    metadata,
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("name", sa.String),
    sa.Column("deployment_type", sa.String),
    sa.Column("db_route", sa.String),
    sa.Column("status", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

users_table = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("organization_id", sa.UUID),
    sa.Column("email", sa.String),
    sa.Column("hashed_password", sa.String),
    sa.Column("full_name", sa.String),
    sa.Column("role", sa.String),
    sa.Column("whatsapp_number", sa.String),
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    deployment_type: str
    db_route: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrganizationProvision(BaseModel):
    name: str
    deployment_type: str
    db_route: str
    admin_name: str
    admin_email: str
    admin_password: str


class OrgUserResponse(BaseModel):
    id: uuid.UUID
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    whatsapp_number: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash_password(plain: str) -> str:
    """Hash password using bcrypt directly (avoids passlib/bcrypt 5.0 incompatibility)."""
    import bcrypt as _bcrypt

    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(_admin: dict = Depends(require_platform_admin)):
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(sa.select(organizations_table))
        rows = result.fetchall()
    return [
        OrganizationResponse(
            id=row.id,
            name=row.name,
            deployment_type=row.deployment_type,
            db_route=row.db_route,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get("/{org_id}/users", response_model=list[OrgUserResponse])
async def list_organization_users(
    org_id: uuid.UUID, _admin: dict = Depends(require_platform_admin)
):
    """Users belonging to one org — powers the "run as" picker in the control-plane
    test harness (admin/system_graph_router.py). Only users with a
    whatsapp_number can actually be simulated; the caller marks the rest as
    untestable."""
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(
                users_table.c.id,
                users_table.c.full_name,
                users_table.c.email,
                users_table.c.role,
                users_table.c.whatsapp_number,
            ).where(users_table.c.organization_id == org_id)
        )
        rows = result.fetchall()
    return [
        OrgUserResponse(
            id=row.id,
            full_name=row.full_name,
            email=row.email,
            role=row.role,
            whatsapp_number=row.whatsapp_number,
        )
        for row in rows
    ]


@router.post("/provision", response_model=OrganizationResponse)
async def provision_tenant(
    prov_in: OrganizationProvision, _admin: dict = Depends(require_platform_admin)
):
    engine = get_engine()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.utcnow()

    async with engine.begin() as conn:  # begin() auto-commits or rolls back
        # 1. Create Organization
        await conn.execute(
            organizations_table.insert().values(
                id=org_id,
                name=prov_in.name,
                deployment_type=prov_in.deployment_type,
                db_route=prov_in.db_route,
                status="Active",
                created_at=now,
                updated_at=now,
            )
        )

        # 2. Create Admin User
        hashed_pwd = _hash_password(prov_in.admin_password)
        try:
            await conn.execute(
                users_table.insert().values(
                    id=user_id,
                    organization_id=org_id,
                    email=prov_in.admin_email,
                    hashed_password=hashed_pwd,
                    full_name=prov_in.admin_name,
                    role="ADMIN",
                    whatsapp_number=None,
                )
            )
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise HTTPException(
                    status_code=400, detail="Admin email is already registered"
                ) from e
            raise HTTPException(status_code=500, detail=f"User creation failed: {e}") from e

    await project_entity("organization", org_id)
    await project_entity("user", user_id)

    return OrganizationResponse(
        id=org_id,
        name=prov_in.name,
        deployment_type=prov_in.deployment_type,
        db_route=prov_in.db_route,
        status="Active",
        created_at=now,
        updated_at=now,
    )
