"""Auth router — login/register for the Mesiri mobile app."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt as _bcrypt
import jwt
import sqlalchemy as sa
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Shared crypto config
# ---------------------------------------------------------------------------
SECRET_KEY = "mesiri-temp-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week


def _hash_pw(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def _verify_pw(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


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
class UserLogin(BaseModel):
    email: str
    password: str


class UserRegister(BaseModel):
    organization_id: str | None = None
    email: str
    password: str
    full_name: str
    role: str = "USER"
    whatsapp_number: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _create_token(user_id: str, org_id: str, role: str, name: str = "", org_name: str = "") -> str:
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "org": org_id,
        "role": role,
        "name": name,
        "org_name": org_name,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/login", response_model=Token)
async def login(creds: UserLogin):
    engine = get_engine()

    # We need the organizations table for the join
    metadata = sa.MetaData()
    organizations_table = sa.Table(
        "organizations",
        metadata,
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column("name", sa.String),
    )

    async with engine.connect() as conn:
        # Join users with organizations to get the org name
        query = (
            sa.select(
                users_table.c.id,
                users_table.c.organization_id,
                users_table.c.hashed_password,
                users_table.c.role,
                users_table.c.full_name,
                organizations_table.c.name.label("org_name"),
            )
            .outerjoin(
                organizations_table, users_table.c.organization_id == organizations_table.c.id
            )
            .where(users_table.c.email == creds.email)
        )

        result = await conn.execute(query)
        row = result.first()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_pw(creds.password, row.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_token(
        user_id=str(row.id),
        org_id=str(row.organization_id) if row.organization_id else "",
        role=row.role,
        name=row.full_name or "",
        org_name=row.org_name or "Independent",
    )
    return Token(access_token=token)


@router.post("/register", response_model=Token)
async def register(user_in: UserRegister):
    engine = get_engine()
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
                organization_id=user_in.organization_id,
                email=user_in.email,
                hashed_password=hashed_pwd,
                full_name=user_in.full_name,
                role=user_in.role,
                whatsapp_number=user_in.whatsapp_number,
            )
        )

    token = _create_token(
        user_id=str(user_id),
        org_id=str(user_in.organization_id) if user_in.organization_id else "",
        role=user_in.role,
    )
    return Token(access_token=token)
