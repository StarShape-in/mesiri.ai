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
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    whatsapp_number: str | None = None

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
        
    return [
        UserResponse(
            id=row.id,
            email=row.email,
            full_name=row.full_name,
            role=row.role,
            whatsapp_number=row.whatsapp_number
        ) for row in rows
    ]

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
            )
        )

    return UserResponse(
        id=user_id,
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role,
        whatsapp_number=user_in.whatsapp_number
    )


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

    return UserResponse(
        id=user_id,
        email=existing.email,
        full_name=values.get("full_name", existing.full_name),
        role=values.get("role", existing.role),
        whatsapp_number=values.get(
            "whatsapp_number",
            existing.whatsapp_number,
        ),
    )
