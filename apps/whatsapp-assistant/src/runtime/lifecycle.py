"""Application lifecycle and FastAPI bootstrap for the WhatsApp assistant."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI

from context.reconcile_watchdog import watchdog_enabled, watchdog_loop
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

            # Context-sync watchdog: dashboard project/site assignment changes
            # are projected into the context layer best-effort (see
            # context/projection_hooks.py, which swallows failures so a
            # projection error can't fail the dashboard request). This
            # periodically re-runs the idempotent reconcile so drift repairs
            # itself, and records every run so a failing watchdog is visible
            # instead of being the same silent failure one level up.
            # A Postgres advisory lock inside the loop keeps the two uvicorn
            # workers (infra/mesiri.service) from both running it.
            reconcile_task = None
            if watchdog_enabled():
                reconcile_task = asyncio.create_task(watchdog_loop())
            else:
                logger.info("Context reconcile watchdog disabled by configuration")

            logger.info("WhatsApp assistant runtime initialized")
            try:
                yield
            finally:
                if reconcile_task is not None:
                    reconcile_task.cancel()
                    # Swallow the CancelledError the task raises on shutdown;
                    # it's the expected way the loop stops, not an error.
                    with suppress(asyncio.CancelledError):
                        await reconcile_task
                await app.state.container.material_db.disconnect()
                await app.state.container.redis_client.disconnect()
                # Only closes anything if a render actually happened (the
                # headless browser launches lazily on first use) -- a no-op
                # otherwise.
                await app.state.container.receipt_renderer.close()

    def _media_storage_provider() -> str:
        """Which object-storage adapter is live, or why we cannot tell."""
        try:
            from mesiri.bootstrap.settings import get_settings

            return str(get_settings().object_storage.provider.value)
        except Exception:  # noqa: BLE001 -- a probe never fails over a label
            return "unknown"


    app = FastAPI(title="Mesiri WhatsApp Assistant", lifespan=lifespan)

    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        # build carries the running commit. Without it there is no way to
        # tell a fix that did not work from a fix that never shipped, which
        # cost days of chasing a bug that had already been fixed.
        #
        # media_storage is here for the same reason. With the fake adapter
        # selected, every photo is written to memory and every URL comes back
        # as memory://, which the dashboard renders as "Photo unavailable" --
        # a symptom that looks like a broken feature and is actually a
        # missing environment variable. The provider name only; never a
        # credential.
        from runtime.build_info import build_sha

        return {
            "status": "ok",
            "build": build_sha(),
            "media_storage": _media_storage_provider(),
        }

    # Alias matching the documented liveness-probe convention
    # (README.md / backend/src/mesiri/http/app.py) -- infra/mesiri.service's
    # deploy health check hits this exact path.
    @app.get("/health/live", tags=["ops"])
    async def health_live() -> dict:
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

    # Context-sync watchdog status/history (platform-admin only)
    try:
        from admin.reconcile_router import router as reconcile_router

        app.include_router(reconcile_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Reconcile router not loaded: %s", exc)

    # Latency/performance viewer (platform-admin only)
    try:
        from admin.perf_router import router as perf_router

        app.include_router(perf_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Perf router not loaded: %s", exc)

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

    # Company / tenant settings routes (dashboard Company Details screen)
    try:
        from mesiri.domains.organizations.router import router as organizations_router

        app.include_router(organizations_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Organizations router not loaded: %s", exc)

    # Expenses routes (dashboard Expenses/Receipts/Categories pages) -- was
    # never wired into this app, only into backend/src/mesiri/http/app.py,
    # which infra/mesiri.service does not actually run (ExecStart is
    # `main:app`, i.e. this create_app()). Every dashboard finance/expense
    # call 404'd in production until this was added.
    try:
        from mesiri.domains.expenses.router import router as expenses_router

        app.include_router(expenses_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Expenses router not loaded: %s", exc)

    # Finance routes (dashboard Accounts/Petty Cash pages) -- same gap as
    # expenses above.
    try:
        from mesiri.domains.finance.router import router as finance_router

        app.include_router(finance_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Finance router not loaded: %s", exc)

    # Vendors routes (dashboard Vendors & Payees page) -- same gap as
    # expenses above.
    try:
        from mesiri.domains.vendors.router import router as vendors_router

        app.include_router(vendors_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Vendors router not loaded: %s", exc)

    # Labour/workforce routes (dashboard Worker Roster, Attendance Log,
    # Overview, Reports, Settings pages; POST /labour/workers add-worker) --
    # same gap as expenses/finance/vendors above: built against
    # backend/src/mesiri/http/app.py, never wired into the app that actually
    # runs. Every dashboard labour call -- including saving a new worker --
    # 404'd in production until this was added (reported by Alan 2026-07-27:
    # "Add Worker" said not found, and a WhatsApp-confirmed attendance never
    # appeared on the dashboard even though it was genuinely saved).
    try:
        from mesiri.domains.workforce.router import router as workforce_router

        app.include_router(workforce_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Workforce router not loaded: %s", exc)

    # Progress/Daily Reporting routes (dashboard Field Reports/Activities
    # pages -- GET /progress/activities, GET /progress/activities/{id}).
    # Mounted here too, not just in backend/src/mesiri/http/app.py, per the
    # lesson immediately above this block: a router that only exists in that
    # file 404s in production, since this file builds the app that actually
    # runs.
    try:
        from mesiri.domains.progress.router import router as progress_router

        app.include_router(progress_router)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Progress router not loaded: %s", exc)

    return app
