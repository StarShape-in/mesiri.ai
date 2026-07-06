"""FastAPI dependency that yields a scoped AsyncConnection per request."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncConnection


async def get_db_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    postgres = request.app.state.lifecycle.container.postgres
    async with postgres.transaction() as conn:
        yield conn
