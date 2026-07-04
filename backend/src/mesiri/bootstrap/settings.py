"""Centralized configuration and secret loading (M1).

One settings object, loaded from environment variables (prefix ``MESIRI_``,
nested delimiter ``__``) and an optional ``.env`` file. Safe defaults exist for
local development only; :meth:`Settings.validate_runtime` fails fast when
required production configuration is missing.

Secrets live only in ``SecretStr`` fields and are never emitted by ``repr`` or
by the logging/health redaction paths.

Ownership: SHARED ARCHITECTURE.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from mesiri_contracts.common.errors import ErrorCode, MesiriError


class Environment(str, Enum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production_like(self) -> bool:
        return self in (Environment.STAGING, Environment.PRODUCTION)


class LogFormat(str, Enum):
    JSON = "json"
    CONSOLE = "console"


class _Section(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")


class LogSettings(_Section):
    level: str = "INFO"
    format: LogFormat = LogFormat.JSON


class PostgresSettings(_Section):
    host: str = "localhost"
    port: int = 5432
    user: str = "mesiri"
    password: SecretStr = SecretStr("mesiri_local_dev")
    database: str = "mesiri"
    pool_min_size: int = 1
    pool_max_size: int = 10
    connect_timeout_seconds: float = 5.0

    def dsn(self, *, driver: str = "postgresql+asyncpg") -> str:
        pwd = self.password.get_secret_value()
        return f"{driver}://{self.user}:{pwd}@{self.host}:{self.port}/{self.database}"

    def safe_dsn(self) -> str:
        """DSN with the password redacted — safe for logs."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.database}"


class RedisSettings(_Section):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None
    namespace: str = "mesiri"
    connect_timeout_seconds: float = 5.0

    def url(self) -> str:
        auth = ""
        if self.password is not None:
            auth = f":{self.password.get_secret_value()}@"
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

    def safe_url(self) -> str:
        auth = ":***@" if self.password is not None else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class ObjectStorageProvider(str, Enum):
    FAKE = "fake"
    R2 = "r2"


class ObjectStorageSettings(_Section):
    provider: ObjectStorageProvider = ObjectStorageProvider.FAKE
    bucket: str = "mesiri-media-local"
    endpoint_url: str | None = None
    access_key_id: SecretStr | None = None
    secret_access_key: SecretStr | None = None
    region: str = "auto"
    presign_ttl_seconds: int = 900


class SarvamSettings(_Section):
    api_key: SecretStr | None = None
    timeout_seconds: float = 7.0
    max_retries: int = 2


class GeminiSettings(_Section):
    api_key: SecretStr | None = None
    model: str = "gemini-2.0-flash"
    timeout_seconds: float = 15.0
    max_retries: int = 2


class WhatsAppSettings(_Section):
    # Owned by M2 (Alan); declared for completeness. Unused by M1/M3.
    verify_token: SecretStr | None = None
    app_secret: SecretStr | None = None
    access_token: SecretStr | None = None
    phone_number_id: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MESIRI_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    service_name: str = "mesiri-assistant"

    log: LogSettings = Field(default_factory=LogSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    object_storage: ObjectStorageSettings = Field(default_factory=ObjectStorageSettings)
    sarvam: SarvamSettings = Field(default_factory=SarvamSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    whatsapp: WhatsAppSettings = Field(default_factory=WhatsAppSettings)

    def validate_runtime(self) -> None:
        """Fail fast for missing *required* production configuration.

        Local/test may rely on safe defaults and the fake object store; a
        production-like environment must supply real secrets and, when R2 is
        selected, complete storage credentials.
        """
        if not self.environment.is_production_like:
            return

        missing: list[str] = []
        default_pg = "mesiri_local_dev"
        if self.postgres.password.get_secret_value() == default_pg:
            missing.append("MESIRI_POSTGRES__PASSWORD (still the local default)")

        if self.object_storage.provider is ObjectStorageProvider.FAKE:
            missing.append("MESIRI_OBJECT_STORAGE__PROVIDER (fake not allowed in production)")
        elif self.object_storage.provider is ObjectStorageProvider.R2:
            for name, val in (
                ("MESIRI_OBJECT_STORAGE__ENDPOINT_URL", self.object_storage.endpoint_url),
                ("MESIRI_OBJECT_STORAGE__ACCESS_KEY_ID", self.object_storage.access_key_id),
                ("MESIRI_OBJECT_STORAGE__SECRET_ACCESS_KEY", self.object_storage.secret_access_key),
            ):
                if not val:
                    missing.append(name)

        if missing:
            raise MesiriError.configuration(
                f"missing required production configuration: {', '.join(missing)}",
                code=ErrorCode.CONFIG_MISSING.value,
                details={"missing": missing, "environment": self.environment.value},
            )


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached settings instance."""
    return Settings()
