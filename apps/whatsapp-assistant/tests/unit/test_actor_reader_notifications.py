"""PostgresActorReader.resolve_whatsapp_id_by_user_id (#9 Notifications) --
only the pure guard is unit-testable without a live DB: a malformed
user_id must return None before ever touching the database."""

from __future__ import annotations

from backend.postgres.actor import PostgresActorReader


async def test_malformed_user_id_returns_none_without_touching_the_db():
    reader = PostgresActorReader(engine="unused -- must never be called")
    result = await reader.resolve_whatsapp_id_by_user_id("not-a-uuid")
    assert result is None
