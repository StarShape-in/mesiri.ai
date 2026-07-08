"""Application dependency wiring for the WhatsApp assistant runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingress.deduplication import InMemoryDeduplicationStore
from ingress.media_ingestion import MetaMediaDownloader
from ingress.receiver import InMemoryNormalizedMessageStore, WhatsAppReceiver

if TYPE_CHECKING:
    from context.resolver import ContextResolver


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
    context_debug: bool = False

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
    context_resolver: ContextResolver
    # redis_client is either a real RedisClient (when MESIRI_REDIS__HOST is set)
    # or FakeRedis for local/test.  Both expose connect() / disconnect() so the
    # lifespan handler can manage the lifecycle without special-casing.
    redis_client: Any


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

    # M4 identity gate, then M2 -> M3 -> M4 Context resolver -> reply.
    import logging as _logging

    from backend.postgres.actor import PostgresActorReader
    from channel.whatsapp.outbound import WhatsAppSender
    from context.live_identity import (
        NO_ORG_MESSAGE,
        ORG_SUSPENDED_MESSAGE,
        UNREGISTERED_MESSAGE,
        resolve_sender,
    )
    from context.runtime import build_context_resolver
    from mesiri.bootstrap.settings import get_settings as _get_backend_settings
    from mesiri.infrastructure.objectstorage import build_object_storage
    from planner import Planner
    from runtime.inbound_journey import process_inbound_message
    from understanding.runtime import build_pipeline, format_reply

    _log = _logging.getLogger("mesiri.context")

    # Object storage: FakeObjectStorage locally, R2 when
    # MESIRI_OBJECT_STORAGE__PROVIDER=r2 is set.
    _backend_settings = _get_backend_settings()
    object_storage = build_object_storage(_backend_settings)

    # Redis for the active context store.  Use a real RedisClient when
    # MESIRI_REDIS__HOST is explicitly configured; fall back to FakeRedis.
    if os.environ.get("MESIRI_REDIS__HOST"):
        from mesiri.infrastructure.redis.client import RedisClient

        redis_client = RedisClient(_backend_settings.redis)
    else:
        from mesiri.infrastructure.redis.client import FakeRedis

        redis_client = FakeRedis()

    pipeline = build_pipeline(object_storage)
    context_resolver = build_context_resolver(redis=redis_client)
    planner = Planner()  # stateless — safe to construct once and share
    sender = WhatsAppSender(
        client=http_client,
        access_token=settings.access_token,
        phone_number_id=settings.phone_number_id,
        api_version=settings.api_version,
        graph_base_url=settings.graph_base_url,
    )

    # Backend capability boundary: create once, reuse the connection pool.
    actor_reader = PostgresActorReader()

    async def _send_understanding_reply(message, understanding) -> None:  # type: ignore[no-untyped-def]
        await sender.send_text(message.sender.wa_id, format_reply(understanding))

    async def _on_normalized(message) -> None:  # type: ignore[no-untyped-def]
        wa_id = message.sender.wa_id

        # M4: resolve the sender before spending on understanding.
        try:
            ctx = await resolve_sender(actor_reader, wa_id)
        except Exception:  # noqa: BLE001 — never let a lookup error drop the message silently
            _log.exception("context.identity_lookup_failed wa_id=%s", wa_id)
            ctx = None

        if ctx is None:
            _log.info("context.sender_unregistered wa_id=%s", wa_id)
            await sender.send_text(wa_id, UNREGISTERED_MESSAGE)
            return

        if ctx.organization_id is None:
            _log.info("context.user_no_org user=%s", ctx.user_id)
            await sender.send_text(wa_id, NO_ORG_MESSAGE.format(name=ctx.full_name))
            return

        if not ctx.org_active:
            _log.info("context.org_suspended org=%s", ctx.organization_id)
            await sender.send_text(wa_id, ORG_SUSPENDED_MESSAGE)
            return

        _log.info(
            "context.resolved user=%s org=%s projects=%s",
            ctx.user_id,
            ctx.organization_id,
            len(ctx.projects),
        )

        await process_inbound_message(
            message,
            pipeline=pipeline,
            context_resolver=context_resolver,
            planner=planner,
            reply_sender=_send_understanding_reply,
            context_debug=settings.context_debug,
        )

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
        context_resolver=context_resolver,
        redis_client=redis_client,
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
