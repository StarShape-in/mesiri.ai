"""Admin router for Control Plane - tenant provisioning."""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine

from context.projection_hooks import project_entity
from mesiri.authorization.roles import ALL_PROJECTS_MODE, is_org_wide
from mesiri.domains.shared.auth import require_platform_admin
from mesiri.domains.timeline.responses import TimelineEntriesListResponse
from mesiri.infrastructure.postgres.repositories.timeline import PostgresTimelineReadRepository

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
    sa.Column("status", sa.String),
    sa.Column("whatsapp_number", sa.String),
    sa.Column("access_policy", sa.JSON),
)

projects_table = sa.Table(
    "projects",
    metadata,
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("organization_id", sa.UUID),
    sa.Column("name", sa.String),
)

sites_table = sa.Table(
    "sites",
    metadata,
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("project_id", sa.UUID),
    sa.Column("organization_id", sa.UUID),
    sa.Column("name", sa.String),
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


class ProjectAccessGrant(BaseModel):
    project_id: uuid.UUID
    project_name: str
    site_access: str


class OrgUserResponse(BaseModel):
    id: uuid.UUID
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    status: str = "Active"
    whatsapp_number: str | None = None
    access_mode: str = "custom_projects"
    project_access: list[ProjectAccessGrant] = []


class UserStatusUpdate(BaseModel):
    status: str


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


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: uuid.UUID, _admin: dict = Depends(require_platform_admin)):
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(organizations_table).where(organizations_table.c.id == org_id)
        )
        row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationResponse(
        id=row.id,
        name=row.name,
        deployment_type=row.deployment_type,
        db_route=row.db_route,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.delete("/{org_id}", status_code=204)
async def delete_organization(org_id: uuid.UUID, _admin: dict = Depends(require_platform_admin)):
    """Hard-delete a tenant and every row scoped to it."""
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.select(organizations_table.c.id).where(organizations_table.c.id == org_id)
        )
        if result.first() is None:
            raise HTTPException(status_code=404, detail="Organization not found")

        org_id_str = str(org_id)

        # 1. Fetch user IDs belonging to this organization
        user_rows = await conn.execute(
            sa.select(users_table.c.id).where(users_table.c.organization_id == org_id)
        )
        user_ids = [r[0] for r in user_rows.fetchall()]
        user_id_strs = [str(uid) for uid in user_ids]

        # 2. Fetch context_user IDs linked to these users
        if user_ids:
            ctx_user_rows = await conn.execute(
                sa.text(
                    "SELECT id FROM context_users WHERE canonical_user_id IN :uids OR id IN :uid_strs"
                ).bindparams(
                    sa.bindparam("uids", expanding=True),
                    sa.bindparam("uid_strs", expanding=True),
                ),
                {"uids": user_ids, "uid_strs": user_id_strs},
            )
            ctx_uids = [r[0] for r in ctx_user_rows.fetchall()]
        else:
            ctx_uids = []

        # 3. Clean user-level context & identity subsystem rows to prevent FK violation on users table deletion
        if ctx_uids or user_ids:
            all_uids_str = list(set(ctx_uids + user_id_strs))
            await conn.execute(
                sa.text(
                    "DELETE FROM user_context_preferences WHERE user_id IN :u_strs"
                ).bindparams(sa.bindparam("u_strs", expanding=True)),
                {"u_strs": all_uids_str},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM site_memberships WHERE user_id IN :u_strs"
                ).bindparams(sa.bindparam("u_strs", expanding=True)),
                {"u_strs": all_uids_str},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM project_memberships WHERE user_id IN :u_strs"
                ).bindparams(sa.bindparam("u_strs", expanding=True)),
                {"u_strs": all_uids_str},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM membership_roles WHERE membership_id IN (SELECT id FROM organization_memberships WHERE user_id IN :u_strs)"
                ).bindparams(sa.bindparam("u_strs", expanding=True)),
                {"u_strs": all_uids_str},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM organization_memberships WHERE user_id IN :u_strs"
                ).bindparams(sa.bindparam("u_strs", expanding=True)),
                {"u_strs": all_uids_str},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM external_identities WHERE user_id IN :u_strs"
                ).bindparams(sa.bindparam("u_strs", expanding=True)),
                {"u_strs": all_uids_str},
            )
            if user_ids:
                await conn.execute(
                    sa.text(
                        "DELETE FROM interactions WHERE user_id IN :uids"
                    ).bindparams(sa.bindparam("uids", expanding=True)),
                    {"uids": user_ids},
                )
            if user_ids:
                await conn.execute(
                    sa.text(
                        "DELETE FROM context_users WHERE canonical_user_id IN :uids OR id IN :u_strs"
                    ).bindparams(
                        sa.bindparam("uids", expanding=True),
                        sa.bindparam("u_strs", expanding=True),
                    ),
                    {"uids": user_ids, "u_strs": all_uids_str},
                )
            else:
                await conn.execute(
                    sa.text(
                        "DELETE FROM context_users WHERE id IN :u_strs"
                    ).bindparams(sa.bindparam("u_strs", expanding=True)),
                    {"u_strs": all_uids_str},
                )

        # 4. Clean org-level context subsystem rows referencing this organization
        ctx_org_rows = await conn.execute(
            sa.text(
                "SELECT id FROM context_organizations WHERE canonical_organization_id = :org_id OR id = :org_id_str"
            ),
            {"org_id": org_id, "org_id_str": org_id_str},
        )
        ctx_ids = [r[0] for r in ctx_org_rows.fetchall()]

        if ctx_ids:
            await conn.execute(
                sa.text(
                    "DELETE FROM user_context_preferences WHERE organization_id IN :ctx_ids"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM site_memberships WHERE site_id IN (SELECT id FROM context_sites WHERE organization_id IN :ctx_ids)"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM project_memberships WHERE project_id IN (SELECT id FROM context_projects WHERE organization_id IN :ctx_ids)"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM context_sites WHERE organization_id IN :ctx_ids"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM context_projects WHERE organization_id IN :ctx_ids"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM membership_roles WHERE membership_id IN (SELECT id FROM organization_memberships WHERE organization_id IN :ctx_ids)"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE organization_id IN :ctx_ids)"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM organization_memberships WHERE organization_id IN :ctx_ids"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM roles WHERE organization_id IN :ctx_ids"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM context_organizations WHERE id IN :ctx_ids OR canonical_organization_id = :org_id"
                ).bindparams(sa.bindparam("ctx_ids", expanding=True)),
                {"ctx_ids": ctx_ids, "org_id": org_id},
            )
        else:
            await conn.execute(
                sa.text(
                    "DELETE FROM context_organizations WHERE canonical_organization_id = :org_id OR id = :org_id_str"
                ),
                {"org_id": org_id, "org_id_str": org_id_str},
            )

        # 5. Delete main organization row (ON DELETE CASCADE sweeps all domain tables)
        try:
            await conn.execute(
                organizations_table.delete().where(organizations_table.c.id == org_id)
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500, detail=f"Failed to delete organization: {exc}"
            ) from exc


@router.get("/{org_id}/timeline", response_model=TimelineEntriesListResponse)
async def list_organization_timeline(
    org_id: uuid.UUID,
    event_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: dict = Depends(require_platform_admin),
):
    """Cross-tenant activity feed for a single organization (platform admin view)."""
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(organizations_table.c.id).where(organizations_table.c.id == org_id)
        )
        if result.first() is None:
            raise HTTPException(status_code=404, detail="Organization not found")

        repo = PostgresTimelineReadRepository(conn)
        items, total = await repo.list_entries(
            organization_id=org_id,
            event_type=event_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    return {"items": items, "total": total}


async def _fetch_org_users(
    conn, org_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> list[OrgUserResponse]:
    query = sa.select(
        users_table.c.id,
        users_table.c.full_name,
        users_table.c.email,
        users_table.c.role,
        users_table.c.status,
        users_table.c.whatsapp_number,
        users_table.c.access_policy,
    ).where(users_table.c.organization_id == org_id)

    if user_id is not None:
        query = query.where(users_table.c.id == user_id)

    result = await conn.execute(query)
    rows = result.fetchall()

    project_rows = await conn.execute(
        sa.select(projects_table.c.id, projects_table.c.name).where(
            projects_table.c.organization_id == org_id
        )
    )
    project_names = {row.id: row.name for row in project_rows.fetchall()}

    site_rows = await conn.execute(
        sa.select(sites_table.c.id, sites_table.c.name).where(
            sites_table.c.organization_id == org_id
        )
    )
    site_names = {row.id: row.name for row in site_rows.fetchall()}

    users = []
    for row in rows:
        policy = row.access_policy or {}
        # An org-wide ROLE is a live bypass that is never written into
        # access_policy or project_members, so reading the stored policy
        # alone under-reported it: an ADMIN carrying the default policy
        # ({"mode": "custom_projects", "projects": []}, set for every user at
        # creation) rendered as "No projects assigned" here while both the
        # WhatsApp assistant and the dashboard gave that same person every
        # project in the org. Under-reporting privilege is the dangerous
        # direction -- an operator auditing access sees "none" and moves on.
        # is_org_wide() is the shared rule every other surface already used.
        mode = (
            ALL_PROJECTS_MODE
            if is_org_wide(row.role, policy)
            else (policy.get("mode") or "custom_projects")
        )
        grants: list[ProjectAccessGrant] = []
        for grant in policy.get("projects") or []:
            if not isinstance(grant, dict):
                continue
            try:
                project_uuid = uuid.UUID(str(grant.get("projectId")))
            except (TypeError, ValueError):
                continue

            site_access = grant.get("siteAccess") or {}
            if site_access.get("mode") == "all_sites":
                site_label = "All Sites"
            else:
                site_ids = site_access.get("siteIds") or []
                names = []
                for site_id in site_ids:
                    try:
                        names.append(site_names.get(uuid.UUID(str(site_id)), str(site_id)))
                    except (TypeError, ValueError):
                        continue
                site_label = ", ".join(names) if names else "No Sites"

            grants.append(
                ProjectAccessGrant(
                    project_id=project_uuid,
                    project_name=project_names.get(project_uuid, str(project_uuid)),
                    site_access=site_label,
                )
            )

        users.append(
            OrgUserResponse(
                id=row.id,
                full_name=row.full_name,
                email=row.email,
                role=row.role,
                status=row.status or "Active",
                whatsapp_number=row.whatsapp_number,
                access_mode=mode,
                project_access=grants,
            )
        )
    return users


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
        return await _fetch_org_users(conn, org_id)


@router.patch("/{org_id}/users/{user_id}/status", response_model=OrgUserResponse)
async def update_organization_user_status(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    _admin: dict = Depends(require_platform_admin),
):
    valid_statuses = {"active", "inactive", "suspended"}
    if body.status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of {sorted(valid_statuses)}",
        )

    normalized_status = body.status.capitalize()
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.select(users_table.c.id).where(
                users_table.c.id == user_id, users_table.c.organization_id == org_id
            )
        )
        if result.first() is None:
            raise HTTPException(status_code=404, detail="User not found in this organization")

        await conn.execute(
            users_table.update()
            .where(users_table.c.id == user_id, users_table.c.organization_id == org_id)
            .values(status=normalized_status)
        )
        fetched = await _fetch_org_users(conn, org_id, user_id)
        if not fetched:
            raise HTTPException(status_code=404, detail="User not found after update")
        return fetched[0]


@router.delete("/{org_id}/users/{user_id}", status_code=204)
async def delete_organization_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    force: bool = Query(default=False),
    _admin: dict = Depends(require_platform_admin),
):
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.select(users_table.c.id).where(
                users_table.c.id == user_id, users_table.c.organization_id == org_id
            )
        )
        if result.first() is None:
            raise HTTPException(status_code=404, detail="User not found in this organization")

        if force:
            user_id_str = str(user_id)
            # Nullify created_by user references in domain tables that have created_by
            for table_name in (
                "money_accounts",
                "money_transactions",
                "expenses",
                "material_receipts",
                "material_usage",
                "material_movements",
                "equipment_events",
                "labour_attendance",
                "timeline_entries",
            ):
                await conn.execute(
                    sa.text(f"UPDATE {table_name} SET created_by = NULL WHERE created_by = :user_id"),
                    {"user_id": user_id},
                )

            # Nullify user_id / actor_user_id in workflow and logging tables
            await conn.execute(
                sa.text("UPDATE workflow_instances SET user_id = NULL WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            await conn.execute(
                sa.text("UPDATE inbound_messages SET actor_user_id = NULL WHERE actor_user_id = :user_id"),
                {"user_id": user_id},
            )

            # Clear context and identity user rows
            await conn.execute(
                sa.text("DELETE FROM user_context_preferences WHERE user_id = :user_id_str"),
                {"user_id_str": user_id_str},
            )
            await conn.execute(
                sa.text("DELETE FROM site_memberships WHERE user_id = :user_id_str"),
                {"user_id_str": user_id_str},
            )
            await conn.execute(
                sa.text("DELETE FROM project_memberships WHERE user_id = :user_id_str"),
                {"user_id_str": user_id_str},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM membership_roles WHERE membership_id IN (SELECT id FROM organization_memberships WHERE user_id = :user_id_str)"
                ),
                {"user_id_str": user_id_str},
            )
            await conn.execute(
                sa.text("DELETE FROM organization_memberships WHERE user_id = :user_id_str"),
                {"user_id_str": user_id_str},
            )
            await conn.execute(
                sa.text("DELETE FROM external_identities WHERE user_id = :user_id_str"),
                {"user_id_str": user_id_str},
            )
            await conn.execute(
                sa.text("DELETE FROM interactions WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            await conn.execute(
                sa.text(
                    "DELETE FROM context_users WHERE canonical_user_id = :user_id OR id = :user_id_str"
                ),
                {"user_id": user_id, "user_id_str": user_id_str},
            )

        try:
            await conn.execute(
                users_table.delete().where(
                    users_table.c.id == user_id, users_table.c.organization_id == org_id
                )
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "foreign key" in msg or "violates" in msg or "constraint" in msg or "23503" in msg:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "User cannot be deleted because they own historical records "
                        "(materials, finance, timeline, etc). Deactivate them instead or use Force Delete."
                    ),
                ) from exc
            raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


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
