"""Users router — tenant user management for the Mesiri app."""

from __future__ import annotations

import os
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
import jwt
import bcrypt as _bcrypt

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
    whatsapp_number: Optional[str] = None

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str
    whatsapp_number: Optional[str] = None

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
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=List[UserResponse])
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
