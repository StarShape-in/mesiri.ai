"""Application dependency wiring for the WhatsApp assistant runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import httpx
from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingress.deduplication import InMemoryDeduplicationStore
from ingress.media_ingestion import MetaMediaDownloader
from ingress.receiver import InMemoryNormalizedMessageStore, WhatsAppReceiver


class Settings(BaseSettings):
    """Environment-backed configuration for WhatsApp ingress."""

    verify_token: str
    app_secret: str
    access_token: str
    phone_number_id: str = ""
    api_version: str = "v21.0"
    graph_base_url: str = "https://graph.facebook.com"
    media_download_dir: str = "/tmp/mesiri/whatsapp-media"
    dedup_ttl_hours: int = 24

    model_config = SettingsConfigDict(
        env_prefix="WHATSAPP_",
        env_file=".env",
        extra="ignore",
    )


@dataclass(slots=True)
class AppContainer:
    """Process-scoped dependency container."""

    settings: Settings
    http_client: httpx.AsyncClient
    deduplication_store: InMemoryDeduplicationStore
    message_store: InMemoryNormalizedMessageStore
    receiver: WhatsAppReceiver


def build_container(settings: Settings, http_client: httpx.AsyncClient) -> AppContainer:
    """Construct the application dependency container."""
    deduplication_store = InMemoryDeduplicationStore(
        ttl=timedelta(hours=settings.dedup_ttl_hours)
    )
    message_store = InMemoryNormalizedMessageStore()
    media_downloader = MetaMediaDownloader(
        client=http_client,
        access_token=settings.access_token,
        api_version=settings.api_version,
        download_dir=Path(settings.media_download_dir),
        graph_base_url=settings.graph_base_url,
    )

    # M2 -> M3 handoff: run the understanding pipeline on each normalized message.
    from channel.whatsapp.outbound import WhatsAppSender
    from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
    from understanding.runtime import build_pipeline, format_reply

    object_storage = FakeObjectStorage()
    pipeline = build_pipeline(object_storage)
    sender = WhatsAppSender(
        client=http_client,
        access_token=settings.access_token,
        phone_number_id=settings.phone_number_id,
        api_version=settings.api_version,
        graph_base_url=settings.graph_base_url,
    )

    async def _on_normalized(message):  # type: ignore[no-untyped-def]
        result = await pipeline.understand(message)
        # Reply with the structured understanding. The Interaction layer (M7)
        # will later replace this with the verify-before-save confirmation flow.
        await sender.send_text(message.sender.wa_id, format_reply(result))

    receiver = WhatsAppReceiver(
        deduplication_store=deduplication_store,
        media_downloader=media_downloader,
        message_store=message_store,
        object_storage=object_storage,
        on_normalized=_on_normalized,
    )
    return AppContainer(
        settings=settings,
        http_client=http_client,
        deduplication_store=deduplication_store,
        message_store=message_store,
        receiver=receiver,
    )


def get_settings(request: Request) -> Settings:
    """Resolve application settings from the dependency container."""
    return get_container(request).settings


def get_container(request: Request) -> AppContainer:
    """Resolve the dependency container from the FastAPI application state."""
    return request.app.state.container


def get_receiver(request: Request) -> WhatsAppReceiver:
    """Resolve the WhatsApp ingress receiver."""
    return get_container(request).receiver
