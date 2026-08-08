"""Resolve an AddProjectMemberCommand's member_name into a real user id.

The WhatsApp chat path only ever supplies a best-effort person-name hint
(`member_name`, e.g. "add Rajesh to the project" -> "Rajesh") -- never an
id, since the AI extraction has no access to the org's real user list. This
needs a DB round trip, hence an injectable port (Handler unit tests supply a
fake instead of hitting Postgres), mirroring
application/automations/name_resolution.py's AudienceNameResolver shape
almost exactly -- singular instead of batch, since a member is added one at
a time -- and reusing the same underlying lookup
(`find_by_full_name_active`) petty_cash's recipient resolution and
automation_setup's audience resolution already rely on.

An unresolved name is always a hard rejection -- there is no "add nobody"
partial-success case the way audience resolution has, so this port returns
the id directly (or None) rather than a result object with two lists.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.repositories.users import PostgresUserRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class MemberNameResolver(ABC):
    @abstractmethod
    async def resolve(
        self, conn: AsyncConnection, *, organization_id: str, name: str
    ) -> str | None:
        """Return the matching active user's id (as a string), or None if no
        active user in this organization has that full name."""
        ...


class PostgresMemberNameResolver(MemberNameResolver):
    async def resolve(
        self, conn: AsyncConnection, *, organization_id: str, name: str
    ) -> str | None:
        repo = PostgresUserRepository(conn)
        user = await repo.find_by_full_name_active(uuid.UUID(organization_id), name)
        return str(user.id) if user else None
