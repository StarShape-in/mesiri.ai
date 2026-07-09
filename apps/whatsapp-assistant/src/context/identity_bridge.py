"""M6.5 identity bridge — deterministic context IDs and canonical lookups."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid5

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


def context_organization_id(canonical_id: UUID) -> str:
    return f"ctx_org_{canonical_id}"


def context_user_id(canonical_id: UUID) -> str:
    return f"ctx_user_{canonical_id}"


def context_project_id(canonical_id: UUID) -> str:
    return f"ctx_proj_{canonical_id}"


def context_site_id(canonical_id: UUID) -> str:
    return f"ctx_site_{canonical_id}"


class IdentityBridgeRepository(Protocol):
    async def canonical_organization_id(self, context_organization_id: str) -> str | None: ...

    async def canonical_user_id(self, context_user_id: str) -> str | None: ...

    async def canonical_project_id(self, context_project_id: str) -> str | None: ...

    async def canonical_site_id(self, context_site_id: str) -> str | None: ...


class PostgresIdentityBridgeRepository:
    """Reads canonical_*_id bridge columns from context entity tables."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def _lookup(self, table: str, column: str, context_id: str) -> str | None:
        from sqlalchemy import text

        from mesiri.infrastructure.errors import map_postgres_error

        sql = f"SELECT {column}::text AS cid FROM {table} WHERE id = :id"
        try:
            async with self._engine.connect() as conn:
                row = (
                    await conn.execute(text(sql), {"id": context_id})
                ).mappings().first()
        except Exception as exc:  # noqa: BLE001
            raise map_postgres_error(exc) from exc
        if row is None or row["cid"] is None:
            return None
        return str(row["cid"])

    async def canonical_organization_id(self, context_organization_id: str) -> str | None:
        return await self._lookup(
            "context_organizations", "canonical_organization_id", context_organization_id
        )

    async def canonical_user_id(self, context_user_id: str) -> str | None:
        return await self._lookup("context_users", "canonical_user_id", context_user_id)

    async def canonical_project_id(self, context_project_id: str) -> str | None:
        return await self._lookup("context_projects", "canonical_project_id", context_project_id)

    async def canonical_site_id(self, context_site_id: str) -> str | None:
        return await self._lookup("context_sites", "canonical_site_id", context_site_id)


FAKE_BRIDGE_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def deterministic_canonical_uuid(context_id: str) -> str:
    """Deterministic canonical UUID for a context id (matches FakeIdentityBridgeRepository)."""
    return str(uuid5(FAKE_BRIDGE_NAMESPACE, context_id))


class FakeIdentityBridgeRepository:
    """Deterministic canonical UUID mapping for unit tests (uuid5 per context id)."""

    _NAMESPACE = FAKE_BRIDGE_NAMESPACE

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self._overrides = overrides or {}

    def _canonical(self, context_id: str) -> str:
        if context_id in self._overrides:
            return self._overrides[context_id]
        return deterministic_canonical_uuid(context_id)

    async def canonical_organization_id(self, context_organization_id: str) -> str | None:
        return self._canonical(context_organization_id)

    async def canonical_user_id(self, context_user_id: str) -> str | None:
        return self._canonical(context_user_id)

    async def canonical_project_id(self, context_project_id: str) -> str | None:
        return self._canonical(context_project_id)

    async def canonical_site_id(self, context_site_id: str) -> str | None:
        return self._canonical(context_site_id)


def build_fake_bridge_from_seed() -> FakeIdentityBridgeRepository:
    """Return a fake bridge; seed context ids map deterministically via uuid5."""
    return FakeIdentityBridgeRepository()
