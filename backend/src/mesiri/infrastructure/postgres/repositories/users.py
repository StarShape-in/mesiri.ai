"""Minimal read-only user lookups shared across domains.

Only `find_by_full_name_active` exists so far -- Finance Module Slice 5's
petty cash resolver is the first caller that needs to turn a free-text
person's name ("Alan") into a real user row (see
application/finance/petty_cash_resolution.py). Every other user access in
this codebase still goes through domains/users/router.py's own inline
table -- this module is not a general users repository, just this one query.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

_users = sa.Table(
    "users",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("full_name", sa.String),
    sa.Column("status", sa.String),
)


@dataclass(frozen=True, slots=True)
class UserSummary:
    id: uuid.UUID
    full_name: str


class PostgresUserRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def find_by_full_name_active(
        self, organization_id: uuid.UUID, full_name: str
    ) -> UserSummary | None:
        """Case-insensitive exact match against active users only."""
        stmt = sa.select(_users).where(
            _users.c.organization_id == organization_id,
            _users.c.status == "active",
            sa.func.lower(_users.c.full_name) == full_name.strip().lower(),
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return UserSummary(id=row["id"], full_name=row["full_name"]) if row else None
