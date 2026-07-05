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
    import logging as _logging

    from channel.whatsapp.outbound import WhatsAppSender
    from context.live_identity import (
        ORG_SUSPENDED_MESSAGE,
        UNREGISTERED_MESSAGE,
        context_header,
        get_engine,
        pick_project,
        resolve_sender,
    )
    from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
    from understanding.adapter import build_pipeline, format_reply, understand

    _log = _logging.getLogger("mesiri.context")
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
        wa_id = message.sender.wa_id

        # M4: WHO is this? Resolve the sender against authoritative data BEFORE
        # spending on understanding, and reject anyone we don't recognise.
        try:
            ctx = await resolve_sender(get_engine(), wa_id)
        except Exception:  # noqa: BLE001 — never let a lookup error drop the message silently
            _log.exception("context.identity_lookup_failed wa_id=%s", wa_id)
            ctx = None

        if ctx is None:
            _log.info("context.sender_unregistered wa_id=%s", wa_id)
            await sender.send_text(wa_id, UNREGISTERED_MESSAGE)
            return
        if not ctx.org_active:
            _log.info("context.org_suspended org=%s", ctx.organization_id)
            await sender.send_text(wa_id, ORG_SUSPENDED_MESSAGE)
            return

        result = await understand(message, pipeline, object_storage)
        project = pick_project(result, ctx.projects)
        _log.info(
            "context.resolved user=%s org=%s project=%s",
            ctx.user_id, ctx.organization_id, project.id if project else None,
        )
        # Reply with the resolved context banner + structured understanding. The
        # Interaction layer (M7) will later add verify-before-save.
        reply = context_header(ctx, project) + "\n\n" + format_reply(result)
        await sender.send_text(wa_id, reply)

    receiver = WhatsAppReceiver(
        deduplication_store=deduplication_store,
        media_downloader=media_downloader,
        message_store=message_store,
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
