"""Composition root / dependency container (M1).

Holds the process-wide initialized infrastructure adapters. Adapters are chosen
from configuration (fake vs real) so the same wiring serves local development,
tests, and production. Nothing here contains business logic — it is pure wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mesiri_contracts.common.storage import ObjectStoragePort

from ..infrastructure.objectstorage import build_object_storage
from ..infrastructure.postgres.database import FakePostgres, PostgresDatabase
from ..infrastructure.redis.client import FakeRedis, RedisClient
from ..observability.health import HealthChecker
from ..observability.logging import StructuredLogger, get_logger
from .settings import ObjectStorageProvider, Settings


@dataclass
class Container:
    settings: Settings
    logger: StructuredLogger
    postgres: PostgresDatabase | FakePostgres
    redis: RedisClient | FakeRedis
    object_storage: ObjectStoragePort
    _extra_probes: list = field(default_factory=list)

    def health_checker(self) -> HealthChecker:
        probes = [self.postgres, self.redis, self.object_storage, *self._extra_probes]
        return HealthChecker(probes)  # type: ignore[arg-type]


def build_container(settings: Settings, *, use_fakes: bool | None = None) -> Container:
    """Assemble the container.

    ``use_fakes`` forces the in-memory adapters (default: inferred — fakes when
    the object-storage provider is ``fake``, which is the local/test default).
    """
    if use_fakes is None:
        use_fakes = settings.object_storage.provider is ObjectStorageProvider.FAKE

    logger = get_logger(settings.service_name)

    postgres: PostgresDatabase | FakePostgres
    redis: RedisClient | FakeRedis
    if use_fakes:
        postgres = FakePostgres()
        redis = FakeRedis(namespace=settings.redis.namespace)
        object_storage: ObjectStoragePort = build_object_storage(settings)
    else:
        postgres = PostgresDatabase(settings.postgres)
        redis = RedisClient(settings.redis)
        object_storage = build_object_storage(settings)

    return Container(
        settings=settings,
        logger=logger,
        postgres=postgres,
        redis=redis,
        object_storage=object_storage,
    )
