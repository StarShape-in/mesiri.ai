"""Unit tests for WhatsApp message deduplication."""

from __future__ import annotations

import pytest

from ingress.deduplication import InMemoryDeduplicationStore


@pytest.mark.asyncio
async def test_deduplication_ignores_duplicate_message_ids() -> None:
    store = InMemoryDeduplicationStore()

    assert await store.try_claim("wamid.123") is True
    assert await store.try_claim("wamid.123") is False
    assert await store.try_claim("wamid.456") is True
