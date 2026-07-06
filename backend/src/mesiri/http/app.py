"""FastAPI application factory exposing liveness and readiness (M1).

Endpoints:
    GET /health/live   -> the process is running (never touches dependencies)
    GET /health/ready  -> can the process reach Postgres, Redis, object storage

A middleware binds the correlation id for every request: it honours an inbound
``X-Correlation-ID`` header (so a journey started upstream stays traceable) or
mints one, and echoes it back. Health responses carry no credentials — only
user-safe dependency states.

Serve with:  uvicorn --factory mesiri.http.app:create_app
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mesiri_contracts.common.health import DependencyState
from mesiri_contracts.common.ids import new_correlation_id

from ..bootstrap.lifecycle import AppLifecycle
from ..observability import tracing

CORRELATION_HEADER = "X-Correlation-ID"


def create_app(lifecycle: AppLifecycle | None = None) -> FastAPI:
    lc = lifecycle or AppLifecycle.create()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await lc.startup()
        try:
            yield
        finally:
            await lc.shutdown()

    app = FastAPI(title="Mesiri Assistant", version="0.1.0", lifespan=lifespan)
    app.state.lifecycle = lc

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        correlation_id = request.headers.get(CORRELATION_HEADER) or new_correlation_id()
        with tracing.correlation_scope(correlation_id=correlation_id):
            response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response

    @app.get("/health/live")
    async def live() -> dict:
        return {"status": "alive", "service": lc.container.settings.service_name}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        report = await lc.container.health_checker().readiness()
        status_code = 200 if report.state == DependencyState.HEALTHY else 503
        return JSONResponse(status_code=status_code, content=report.model_dump())

    # CORS Configuration
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    try:
        from mesiri.domains.identity.router import router as identity_router
        app.include_router(identity_router)
    except ImportError:
        pass

    try:
        from mesiri.domains.admin.router import router as admin_router
        app.include_router(admin_router)
    except ImportError:
        pass

    try:
        from mesiri.domains.users.router import router as users_router
        app.include_router(users_router)
    except ImportError:
        pass

    try:
        from mesiri.domains.projects.router import router as projects_router
        app.include_router(projects_router)
    except ImportError:
        pass

    return app
