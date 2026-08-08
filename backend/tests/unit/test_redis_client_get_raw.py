"""Unit test for RedisClient/FakeRedis's raw (non-namespaced) string read.

get_raw() was added for admin/queue_router.py (apps/whatsapp-assistant) to
read ARQ's own health-check key, which the ARQ Worker writes as a plain
string via psetex -- not one of this client's own namespaced JSON values.
"""

from __future__ import annotations

import pytest

from mesiri.infrastructure.redis.client import FakeRedis


@pytest.mark.asyncio
async def test_get_raw_returns_none_for_a_missing_key() -> None:
    redis = FakeRedis()
    await redis.connect()

    assert await redis.get_raw("some:key") is None


@pytest.mark.asyncio
async def test_get_raw_reads_a_plain_string_value_unnamespaced() -> None:
    """get_raw must read the exact key given -- no namespace prefix -- since
    it's meant for values other processes (e.g. ARQ) wrote themselves."""
    redis = FakeRedis(namespace="mesiri")
    await redis.connect()
    redis._store["mesiri:whatsapp:ingress:health-check"] = "Aug-08 12:00:00 j_complete=1"

    value = await redis.get_raw("mesiri:whatsapp:ingress:health-check")

    assert value == "Aug-08 12:00:00 j_complete=1"
