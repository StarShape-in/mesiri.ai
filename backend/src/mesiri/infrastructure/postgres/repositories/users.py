"""Minimal read-only user lookups shared across domains.

`find_by_full_name_active` exists since Finance Module Slice 5's petty cash
resolver, the first caller that needed to turn a free-text person's name
("Alan") into a real user row (see application/finance/
petty_cash_resolution.py). `list_active` exists for
runtime/entity_resolution/member_resolution.py's near-match scoring, which
needs the whole active roster to score against, not just an exact-match
probe -- an org's active-user count is small (dozens, not thousands), so an
in-Python scan is fine; see workforce_query.py's identical reasoning for the
worker register. Every other user access in this codebase still goes through
domains/users/router.py's own inline table -- this module is not a general
users repository, just these two queries.
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

    async def list_active(self, organization_id: uuid.UUID) -> list[UserSummary]:
        """Every active user in the org, for near-match scoring against a
        free-text name hint (member_resolution.py) -- not filtered or
        paginated, since scoring needs the whole roster in memory at once."""
        stmt = sa.select(_users).where(
            _users.c.organization_id == organization_id,
            _users.c.status == "active",
        )
        res = await self.conn.execute(stmt)
        return [UserSummary(id=row["id"], full_name=row["full_name"]) for row in res.mappings()]
