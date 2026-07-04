"""Application lifecycle: clean startup and shutdown (M1).

Startup order:
    validate configuration -> initialize logging -> connect Postgres ->
    connect Redis -> connect object storage -> ready.

Shutdown reverses the resource order and always attempts every close, so one
failing close does not strand the others. A failed startup rolls back any
resources already opened.
"""

from __future__ import annotations

from mesiri_contracts.common.errors import MesiriError

from ..observability.logging import configure_logging
from .container import Container, build_container
from .settings import Settings, get_settings


class AppLifecycle:
    def __init__(self, container: Container) -> None:
        self.container = container
        self._started = False

    @classmethod
    def create(cls, settings: Settings | None = None, *, use_fakes: bool | None = None) -> AppLifecycle:
        settings = settings or get_settings()
        settings.validate_runtime()          # fail fast before touching anything
        configure_logging(settings)          # logging ready before adapters emit
        container = build_container(settings, use_fakes=use_fakes)
        return cls(container)

    async def startup(self) -> None:
        c = self.container
        log = c.logger
        opened: list = []
        try:
            log.info("lifecycle.startup.begin", environment=c.settings.environment.value)
            await c.postgres.connect()
            opened.append(c.postgres)
            log.info("lifecycle.postgres.connected", dsn=c.settings.postgres.safe_dsn())

            await c.redis.connect()
            opened.append(c.redis)
            log.info("lifecycle.redis.connected", url=c.settings.redis.safe_url())

            # Object storage adapters connect lazily; verify reachability now.
            await c.object_storage.check_health()  # type: ignore[attr-defined]
            log.info("lifecycle.object_storage.ready",
                     provider=c.settings.object_storage.provider.value)

            self._started = True
            log.info("lifecycle.startup.complete")
        except MesiriError as err:
            log.error("lifecycle.startup.failed", error=err)
            for resource in reversed(opened):
                try:
                    await resource.disconnect()
                except Exception:  # noqa: BLE001 — best-effort rollback
                    pass
            raise

    async def shutdown(self) -> None:
        c = self.container
        log = c.logger
        log.info("lifecycle.shutdown.begin")
        for name, resource in (
            ("object_storage", c.object_storage),
            ("redis", c.redis),
            ("postgres", c.postgres),
        ):
            disconnect = getattr(resource, "disconnect", None)
            if disconnect is None:
                continue
            try:
                await disconnect()
                log.info("lifecycle.shutdown.closed", dependency=name)
            except Exception as exc:  # noqa: BLE001 — always attempt every close
                log.warning("lifecycle.shutdown.close_failed", dependency=name, detail=str(exc))
        self._started = False
        log.info("lifecycle.shutdown.complete")

    @property
    def started(self) -> bool:
        return self._started
