"""Resolve a CreateAutomationCommand's audience_names into real user ids.

The WhatsApp chat path only ever supplies best-effort person-name hints
(`audience_names`, e.g. "ask Ilan or Hysam" -> ["Ilan", "Hysam"]) -- never
ids, since the AI extraction has no access to the org's real user list. This
needs a DB round trip, hence an injectable port (Handler unit tests supply a
fake instead of hitting Postgres), mirroring
application/finance/resolution.py's AccountLookupResolver shape and reusing
the exact lookup (`find_by_full_name_active`) petty_cash's recipient
resolution already relies on.

Unlike finance's resolver, an unresolved name here is not necessarily a hard
rejection by itself -- the Handler decides that (see handlers.py) -- this
module only reports which names matched and which didn't.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.repositories.users import PostgresUserRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class NameResolutionResult:
    resolved_user_ids: list[str]
    unresolved_names: list[str]


class AudienceNameResolver(ABC):
    @abstractmethod
    async def resolve(
        self, conn: AsyncConnection, *, organization_id: str, names: list[str]
    ) -> NameResolutionResult: ...


class PostgresAudienceNameResolver(AudienceNameResolver):
    async def resolve(
        self, conn: AsyncConnection, *, organization_id: str, names: list[str]
    ) -> NameResolutionResult:
        repo = PostgresUserRepository(conn)
        org_uuid = uuid.UUID(organization_id)
        resolved: list[str] = []
        unresolved: list[str] = []
        for name in names:
            user = await repo.find_by_full_name_active(org_uuid, name)
            if user is None:
                unresolved.append(name)
            else:
                resolved.append(str(user.id))
        return NameResolutionResult(resolved_user_ids=resolved, unresolved_names=unresolved)
