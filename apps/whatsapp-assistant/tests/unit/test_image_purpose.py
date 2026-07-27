"""interactions/image_purpose.py — unit tests (fake store, no real Redis).

#2 Batch Media: a burst of photos must get exactly ONE picker, not one per
photo -- covered here alongside the original single-photo/non-image cases.
"""

from __future__ import annotations

from datetime import UTC, datetime

from interactions.image_purpose import try_hold_new_image_for_purpose_picker
from interactions.pending_media import MAX_BATCH_SIZE, PendingMediaStore
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import (
    MediaReference,
    NormalizedMessage,
    SenderInfo,
)

USR = "22222222-2222-4222-8222-222222222222"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value, *, ttl_seconds=None) -> None:
        self._store[key] = value

    async def get_json(self, key: str):
        return self._store.get(key)


def _message(
    modality: InputModality, text: str | None = None, message_id: str = "wamid.1"
) -> NormalizedMessage:
    return NormalizedMessage(
        message_id=message_id,
        correlation_id="cor_1",
        sender=SenderInfo(wa_id="919000000000", profile_name="Ravi"),
        timestamp=datetime(2026, 7, 25, 10, 0, tzinfo=UTC),
        modality=modality,
        text=text,
        media=MediaReference(
            object_key=f"media/{message_id}/abc123", mime_type="image/jpeg", size_bytes=1024
        )
        if modality is InputModality.IMAGE
        else None,
    )


async def test_new_image_is_held_and_returns_the_picker():
    store = PendingMediaStore(_FakeRedis())

    reply = await try_hold_new_image_for_purpose_picker(
        _message(InputModality.IMAGE), user_id=USR, pending_media_store=store
    )

    assert reply is not None
    assert "photo" in reply.text.lower()
    assert reply.list_rows is not None
    row_ids = {row.id for row in reply.list_rows}
    assert row_ids == {"img_expense", "img_attendance", "img_site_update"}

    held = await store.pop_batch(user_id=USR)
    assert len(held) == 1
    assert held[0].media.object_key == "media/wamid.1/abc123"


async def test_text_message_is_ignored():
    store = PendingMediaStore(_FakeRedis())
    reply = await try_hold_new_image_for_purpose_picker(
        _message(InputModality.TEXT, text="spent 250 on fuel"), user_id=USR, pending_media_store=store
    )
    assert reply is None
    assert await store.pop_batch(user_id=USR) == []


async def test_interactive_tap_is_ignored():
    """A tap answering the picker is InputModality.INTERACTIVE, not IMAGE --
    it must never re-trigger the hold gate."""
    store = PendingMediaStore(_FakeRedis())
    reply = await try_hold_new_image_for_purpose_picker(
        _message(InputModality.INTERACTIVE), user_id=USR, pending_media_store=store
    )
    assert reply is None


async def test_a_burst_of_photos_gets_exactly_one_picker():
    store = PendingMediaStore(_FakeRedis())

    first = await try_hold_new_image_for_purpose_picker(
        _message(InputModality.IMAGE, message_id="wamid.1"), user_id=USR, pending_media_store=store
    )
    second = await try_hold_new_image_for_purpose_picker(
        _message(InputModality.IMAGE, message_id="wamid.2"), user_id=USR, pending_media_store=store
    )
    third = await try_hold_new_image_for_purpose_picker(
        _message(InputModality.IMAGE, message_id="wamid.3"), user_id=USR, pending_media_store=store
    )

    assert first is not None  # the picker
    assert second is None  # silently appended
    assert third is None  # silently appended

    held = await store.pop_batch(user_id=USR)
    assert len(held) == 3
    assert {m.message_id for m in held} == {"wamid.1", "wamid.2", "wamid.3"}


async def test_exceeding_the_cap_replies_with_an_honest_note_once():
    store = PendingMediaStore(_FakeRedis())
    for i in range(MAX_BATCH_SIZE):
        await try_hold_new_image_for_purpose_picker(
            _message(InputModality.IMAGE, message_id=f"wamid.{i}"),
            user_id=USR,
            pending_media_store=store,
        )

    overflow_reply = await try_hold_new_image_for_purpose_picker(
        _message(InputModality.IMAGE, message_id="wamid.overflow"),
        user_id=USR,
        pending_media_store=store,
    )

    assert overflow_reply is not None
    assert str(MAX_BATCH_SIZE) in overflow_reply.text
    assert overflow_reply.list_rows is None  # a note, not another picker

    held = await store.pop_batch(user_id=USR)
    assert len(held) == MAX_BATCH_SIZE
