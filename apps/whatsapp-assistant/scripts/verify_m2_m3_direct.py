"""Verify M2 -> M3 works without understanding/adapter.py."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "shared" / "contracts" / "src"),
    str(ROOT / "platform" / "ai" / "src"),
    str(ROOT / "backend" / "src"),
    str(ROOT / "apps" / "whatsapp-assistant" / "src"),
    str(ROOT / "apps" / "whatsapp-assistant" / "tests"),
]

assert importlib.util.find_spec("understanding.adapter") is None
assert importlib.util.find_spec("understanding.inbound") is None

from fixtures.meta_payloads import text_webhook_payload, voice_webhook_payload

from ingress.deduplication import InMemoryDeduplicationStore
from ingress.media_ingestion import DownloadedMedia
from ingress.receiver import InMemoryNormalizedMessageStore, WhatsAppReceiver
from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai import fixtures
from mesiri_ai.fakes import FakeExtractionProvider, FakeSpeechProvider, FakeVisionProvider
from mesiri_contracts.assistant.enums import InputModality
from understanding.pipeline import UnderstandingPipeline


async def main() -> None:
    storage = FakeObjectStorage()
    pipeline = UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.JCB_EQUIPMENT_EXTRACTION),
        object_storage=storage,
    )
    results = []

    async def on_normalized(msg, raw_payload=None, retry_of_id=None):
        assert not hasattr(msg, "content")
        assert not hasattr(msg, "message_type")
        result = await pipeline.understand(msg)
        results.append(result)
        print(
            f"OK direct pipeline: modality={msg.modality.value} "
            f"correlation={result.correlation_id} semantic={result.semantic_type.value}"
        )

    store = InMemoryNormalizedMessageStore()
    receiver = WhatsAppReceiver(
        deduplication_store=InMemoryDeduplicationStore(),
        media_downloader=AsyncMock(),
        message_store=store,
        object_storage=storage,
        on_normalized=on_normalized,
    )

    await receiver.handle_payload(text_webhook_payload())
    await receiver.wait_until_idle()
    text_msg = await store.get("wamid.text")
    assert text_msg is not None
    assert text_msg.text == "Installed 20 bags of cement"
    assert text_msg.modality is InputModality.TEXT

    voice_file = Path(__file__).resolve().parent / "_voice_test.ogg"
    voice_file.write_bytes(b"fake-voice")
    receiver._media_downloader.download.return_value = DownloadedMedia(
        media_id="media-audio-1",
        mime_type="audio/ogg",
        file_path=str(voice_file),
        sha256="x",
        file_size=10,
    )
    await receiver.handle_payload(voice_webhook_payload(message_id="wamid.voice-e2e"))
    await receiver.wait_until_idle()
    voice_msg = await store.get("wamid.voice-e2e")
    assert voice_msg is not None and voice_msg.media is not None
    assert voice_msg.media.object_key.startswith("media/wamid.voice-e2e/")
    stored = await storage.get_object(voice_msg.media.object_key)
    assert stored.data == b"fake-voice"
    assert len(results) == 2
    assert results[1].candidates[0].fields.get("equipment_name") == "JCB"
    voice_file.unlink(missing_ok=True)
    print("E2E M2->M3 without adapter: PASSED")


if __name__ == "__main__":
    asyncio.run(main())
