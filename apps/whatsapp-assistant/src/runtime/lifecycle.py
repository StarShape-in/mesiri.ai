"""Application lifecycle and FastAPI bootstrap for the WhatsApp assistant."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from ingress.webhook import router as webhook_router
from runtime.dependencies import Settings, build_container

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure process-wide logging defaults."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application for the WhatsApp assistant."""
    configure_logging()
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialize and tear down shared runtime dependencies."""
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            app.state.container = build_container(app_settings, http_client)
            logger.info("WhatsApp assistant runtime initialized")
            yield

    app = FastAPI(title="Mesiri WhatsApp Assistant", lifespan=lifespan)
    app.include_router(webhook_router, prefix="/webhook")
    return app
