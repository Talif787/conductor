"""Alembic async migration environment."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context

from app.config.settings import get_settings
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.session import create_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Offline mode emits SQL without connecting, so the raw URL string is fine
    # here (no driver, so libpq params and SSL are irrelevant).
    context.configure(
        url=get_settings().database.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # Build the engine through the app's create_engine so migrations connect
    # exactly like the app: libpq-only params (sslmode, channel_binding) are
    # stripped and TLS is applied per CONDUCTOR_DB_SSL. This is what makes
    # `alembic upgrade head` work against managed Postgres (Neon) at deploy.
    connectable = create_engine(get_settings().database)
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
