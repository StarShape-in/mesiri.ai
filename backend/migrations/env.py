"""Alembic environment (M1).

The database URL is taken from Mesiri :class:`Settings` (never hard-coded), and
migrations run synchronously via a psycopg-style URL derived from the async DSN.
Only M1 infrastructure migrations exist yet — later-milestone domain schemas are
deliberately not created here.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from mesiri.bootstrap.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the runtime URL. Alembic uses a synchronous driver.
settings = get_settings()
sync_url = settings.postgres.dsn(driver="postgresql+psycopg")
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = None  # migrations are hand-written; no ORM autogenerate yet


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
