"""FastAPI dependency that yields a scoped AsyncConnection per request."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncConnection


async def get_db_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    if hasattr(request.app.state, "lifecycle"):
        postgres = request.app.state.lifecycle.container.postgres
    elif hasattr(request.app.state, "container"):
        postgres = request.app.state.container.material_db
    else:
        # Fallback to creating/connecting database on the fly if needed
        from mesiri.bootstrap.settings import get_settings
        from mesiri.infrastructure.postgres.database import PostgresDatabase
        settings = get_settings()
        postgres = PostgresDatabase(settings.postgres)
        await postgres.connect()
        async with postgres.transaction() as conn:
            yield conn
        await postgres.disconnect()
        return

    async with postgres.transaction() as conn:
        yield conn
