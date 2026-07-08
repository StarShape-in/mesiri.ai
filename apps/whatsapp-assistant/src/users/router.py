"""Users router — tenant user management for the Mesiri app."""

from __future__ import annotations

import os
import uuid

import bcrypt as _bcrypt
import jwt
import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine

router = APIRouter(prefix="/users", tags=["users"])

# ---------------------------------------------------------------------------
# Shared crypto config
# ---------------------------------------------------------------------------
SECRET_KEY = "mesiri-temp-secret-key-change-in-production"
ALGORITHM = "HS256"

def _hash_pw(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()

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

# Raw table reference
users_table = sa.Table(
    "users",
    sa.MetaData(),
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("organization_id", sa.UUID),
    sa.Column("email", sa.String),
    sa.Column("hashed_password", sa.String),
    sa.Column("full_name", sa.String),
    sa.Column("role", sa.String),
    sa.Column("whatsapp_number", sa.String),
    sa.Column("status", sa.String),
    sa.Column("access_policy", sa.JSON),
)

_DEFAULT_ACCESS_POLICY: dict = {"mode": "custom_projects", "projects": []}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    whatsapp_number: str | None = None
    status: str
    access_policy: dict | None = None

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str
    whatsapp_number: str | None = None

class UserUpdate(BaseModel):
    """Partial update — only provided fields are changed. Email is immutable."""
    full_name: str | None = None
    role: str | None = None
    whatsapp_number: str | None = None
    password: str | None = None

class StatusUpdate(BaseModel):
    status: str

class AccessPolicy(BaseModel):
    mode: str
    projects: list[dict] | None = None

def _row_to_response(row) -> UserResponse:
    return UserResponse(
        id=row.id,
        email=row.email,
        full_name=row.full_name,
        role=row.role,
        whatsapp_number=row.whatsapp_number,
        status=row.status or "active",
        access_policy=row.access_policy or _DEFAULT_ACCESS_POLICY,
    )

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
async def get_current_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "ADMIN":
            raise HTTPException(status_code=403, detail="Not authorized (Admin only)")
        return payload
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=list[UserResponse])
async def list_users(admin_payload: dict = Depends(get_current_admin)):
    engine = get_engine()
    org_id = admin_payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="Admin has no organization")

    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(users_table).where(users_table.c.organization_id == org_id)
        )
        rows = result.fetchall()
        
    return [_row_to_response(row) for row in rows]

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    admin_payload: dict = Depends(get_current_admin)
):
    engine = get_engine()
    org_id = admin_payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="Admin has no organization")

    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(users_table).where(
                users_table.c.id == user_id,
                users_table.c.organization_id == org_id,
            )
        )
        row = result.first()
        
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_response(row)


@router.post("", response_model=UserResponse)
async def create_user(user_in: UserCreate, admin_payload: dict = Depends(get_current_admin)):
    engine = get_engine()
    org_id = admin_payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="Admin has no organization")

    valid_roles = ["ADMIN", "PROJECT_MANAGER", "SITE_ENGINEER", "FINANCE"]
    if user_in.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {valid_roles}")

    user_id = uuid.uuid4()
    async with engine.begin() as conn:
        # Check existing
        result = await conn.execute(
            sa.select(users_table).where(users_table.c.email == user_in.email)
        )
        if result.first():
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_pwd = _hash_pw(user_in.password)
        await conn.execute(
            users_table.insert().values(
                id=user_id,
                organization_id=org_id,
                email=user_in.email,
                hashed_password=hashed_pwd,
                full_name=user_in.full_name,
                role=user_in.role,
                whatsapp_number=user_in.whatsapp_number,
                status="active",
                access_policy=_DEFAULT_ACCESS_POLICY,
            )
        )

    async with engine.connect() as conn:
        result = await conn.execute(sa.select(users_table).where(users_table.c.id == user_id))
        row = result.first()
    return _row_to_response(row)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    admin_payload: dict = Depends(get_current_admin),
):
    engine = get_engine()
    org_id = admin_payload.get("org")
    if not org_id:
        raise HTTPException(status_code=400, detail="Admin has no organization")

    if user_in.role is not None:
        valid_roles = ["ADMIN", "PROJECT_MANAGER", "SITE_ENGINEER", "FINANCE"]
        if user_in.role not in valid_roles:
            raise HTTPException(
                status_code=400, detail=f"Invalid role. Must be one of {valid_roles}"
            )

    # Build the set of changes from provided fields only.
    values: dict = {}
    if user_in.full_name is not None:
        values["full_name"] = user_in.full_name
    if user_in.role is not None:
        values["role"] = user_in.role
    if user_in.whatsapp_number is not None:
        # Empty string clears the number; otherwise store the trimmed value.
        values["whatsapp_number"] = user_in.whatsapp_number.strip() or None
    if user_in.password:
        values["hashed_password"] = _hash_pw(user_in.password)

    async with engine.begin() as conn:
        # Tenant-scoped lookup: an admin can only edit users in their own org.
        result = await conn.execute(
            sa.select(users_table).where(
                users_table.c.id == user_id,
                users_table.c.organization_id == org_id,
            )
        )
        existing = result.first()
        if existing is None:
            raise HTTPException(status_code=404, detail="User not found")

        if values:
            await conn.execute(
                users_table.update()
                .where(
                    users_table.c.id == user_id,
                    users_table.c.organization_id == org_id,
                )
                .values(**values)
            )

    async with engine.connect() as conn:
        result = await conn.execute(sa.select(users_table).where(users_table.c.id == user_id))
        row = result.first()
    return _row_to_response(row)


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: uuid.UUID,
    body: StatusUpdate,
    admin_payload: dict = Depends(get_current_admin),
):
    engine = get_engine()
    org_id = admin_payload.get("org")
    valid_statuses = {"active", "inactive", "suspended", "invited"}
    
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {sorted(valid_statuses)}")

    async with engine.begin() as conn:
        result = await conn.execute(
            sa.select(users_table).where(
                users_table.c.id == user_id,
                users_table.c.organization_id == org_id,
            )
        )
        if result.first() is None:
            raise HTTPException(status_code=404, detail="User not found")

        await conn.execute(
            users_table.update()
            .where(
                users_table.c.id == user_id,
                users_table.c.organization_id == org_id,
            )
            .values(status=body.status)
        )

    async with engine.connect() as conn:
        result = await conn.execute(sa.select(users_table).where(users_table.c.id == user_id))
        row = result.first()
    return _row_to_response(row)


@router.get("/{user_id}/access", response_model=AccessPolicy)
async def get_user_access(
    user_id: uuid.UUID,
    admin_payload: dict = Depends(get_current_admin),
):
    engine = get_engine()
    org_id = admin_payload.get("org")
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(users_table.c.access_policy).where(
                users_table.c.id == user_id,
                users_table.c.organization_id == org_id,
            )
        )
        row = result.first()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")

    policy = row.access_policy or _DEFAULT_ACCESS_POLICY
    return AccessPolicy(**policy)


@router.put("/{user_id}/access", response_model=AccessPolicy)
async def update_user_access(
    user_id: uuid.UUID,
    policy: AccessPolicy,
    admin_payload: dict = Depends(get_current_admin),
):
    engine = get_engine()
    org_id = admin_payload.get("org")
    
    if policy.mode not in ("all_projects", "custom_projects"):
        raise HTTPException(
            status_code=400, detail="mode must be 'all_projects' or 'custom_projects'"
        )

    async with engine.begin() as conn:
        result = await conn.execute(
            sa.select(users_table.c.id).where(
                users_table.c.id == user_id,
                users_table.c.organization_id == org_id,
            )
        )
        if result.first() is None:
            raise HTTPException(status_code=404, detail="User not found")

        await conn.execute(
            users_table.update()
            .where(
                users_table.c.id == user_id,
                users_table.c.organization_id == org_id,
            )
            .values(access_policy=policy.model_dump())
        )
    return policy
