"""PostgreSQL implementation of AI configuration repository."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresAIConfigRepository:
    """PostgreSQL implementation of AI configuration repository.

    Manages active AI capability routes and provider secret settings (API keys, base URLs).
    """

    def __init__(self, conn: AsyncConnection):
        """Initialize with database connection."""
        self._conn = conn

        self._active_routes = sa.Table(
            "ai_active_routes",
            sa.MetaData(),
            sa.Column("capability", sa.String, primary_key=True),
            sa.Column("provider_id", sa.String, nullable=False),
            sa.Column("model", sa.String, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
        )

        self._provider_secrets = sa.Table(
            "ai_provider_secrets",
            sa.MetaData(),
            sa.Column("provider_id", sa.String, primary_key=True),
            sa.Column("api_key", sa.String, nullable=False),
            sa.Column("base_url", sa.String, nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
        )

    async def get_active_routes(self) -> dict[str, dict[str, str]]:
        """Retrieve all active capability routes."""
        query = sa.select(
            self._active_routes.c.capability,
            self._active_routes.c.provider_id,
            self._active_routes.c.model,
        )
        result = await self._conn.execute(query)
        rows = result.fetchall()
        return {
            row.capability: {
                "provider_id": row.provider_id,
                "model": row.model,
            }
            for row in rows
        }

    async def get_provider_secrets(self) -> dict[str, dict[str, str | None]]:
        """Retrieve all configured provider secrets."""
        query = sa.select(
            self._provider_secrets.c.provider_id,
            self._provider_secrets.c.api_key,
            self._provider_secrets.c.base_url,
        )
        result = await self._conn.execute(query)
        rows = result.fetchall()
        return {
            row.provider_id: {
                "api_key": row.api_key,
                "base_url": row.base_url,
            }
            for row in rows
        }

    async def update_active_route(self, capability: str, provider_id: str, model: str) -> None:
        """Upsert an active route for a capability."""
        # PostgreSQL UPSERT (ON CONFLICT DO UPDATE)
        insert_stmt = pg_insert(self._active_routes).values(
            capability=capability,
            provider_id=provider_id,
            model=model,
        )
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["capability"],
            set_={"provider_id": provider_id, "model": model, "updated_at": sa.func.now()},
        )
        await self._conn.execute(stmt)

    async def update_provider_secret(self, provider_id: str, api_key: str, base_url: str | None = None) -> None:
        """Upsert secret details for a provider."""
        insert_stmt = pg_insert(self._provider_secrets).values(
            provider_id=provider_id,
            api_key=api_key,
            base_url=base_url,
        )
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["provider_id"],
            set_={"api_key": api_key, "base_url": base_url, "updated_at": sa.func.now()},
        )
        await self._conn.execute(stmt)
