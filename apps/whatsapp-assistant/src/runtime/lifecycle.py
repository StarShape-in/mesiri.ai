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
            # Connect the Redis client (no-op for FakeRedis; real connection
            # for RedisClient when MESIRI_REDIS__HOST is configured).
            await app.state.container.redis_client.connect()
            # M8: connect the Material execution transaction owner.
            await app.state.container.material_db.connect()
            logger.info("WhatsApp assistant runtime initialized")
            try:
                yield
            finally:
                await app.state.container.material_db.disconnect()
                await app.state.container.redis_client.disconnect()
                # Only closes anything if a render actually happened (the
                # headless browser launches lazily on first use) -- a no-op
                # otherwise.
                await app.state.container.receipt_renderer.close()

    app = FastAPI(title="Mesiri WhatsApp Assistant", lifespan=lifespan)

    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(webhook_router, prefix="/webhook")

    # CORS for Control Plane dashboard
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Admin / Control Plane routes
    try:
        from admin.router import router as admin_router

        app.include_router(admin_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Admin router not loaded: %s", exc)

    # WhatsApp assistant log viewer (platform-admin only)
    try:
        from admin.logs_router import router as logs_router

        app.include_router(logs_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Logs router not loaded: %s", exc)

    # System graph — assistant pipeline visualization (platform-admin only)
    try:
        from admin.system_graph_router import router as system_graph_router

        app.include_router(system_graph_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("System graph router not loaded: %s", exc)

    # AI Providers visibility (platform-admin only)
    try:
        from mesiri.domains.admin.providers_router import router as providers_router

        app.include_router(providers_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Providers router not loaded: %s", exc)

    # Platform-admin account management (platform-admin only)
    try:
        from admin.platform_users_router import router as platform_users_router

        app.include_router(platform_users_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Platform users router not loaded: %s", exc)

    # Auth routes (mobile app login/register)
    try:
        from auth.router import router as auth_router

        app.include_router(auth_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Auth router not loaded: %s", exc)

    # Users routes (tenant management)
    try:
        from users.router import router as users_router

        app.include_router(users_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Users router not loaded: %s", exc)

    # Projects routes (tenant-scoped project management)
    try:
        from projects.router import router as projects_router

        app.include_router(projects_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Projects router not loaded: %s", exc)

    # Materials routes (tenant-scoped materials log)
    try:
        from mesiri.domains.materials.router import router as materials_router

        app.include_router(materials_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Materials router not loaded: %s", exc)

    # Timeline routes
    try:
        from mesiri.domains.timeline.router import router as timeline_router

        app.include_router(timeline_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Timeline router not loaded: %s", exc)

    return app
