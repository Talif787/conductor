"""Async engine and session factory construction."""

from __future__ import annotations

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import DatabaseSettings

# libpq-style query params that asyncpg does not accept as connect kwargs.
# They are stripped from the URL; TLS is configured via connect_args instead.
_LIBPQ_ONLY_PARAMS = frozenset({"sslmode", "channel_binding", "ssl"})


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    url = make_url(settings.url)
    if url.query:
        cleaned = {k: v for k, v in url.query.items() if k not in _LIBPQ_ONLY_PARAMS}
        url = url.set(query=cleaned)

    connect_args: dict[str, object] = {}
    if settings.ssl:
        # "require" encrypts the connection without enforcing CA verification,
        # matching libpq sslmode=require. Managed Postgres (Neon) needs TLS.
        connect_args["ssl"] = "require"

    return create_async_engine(
        url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout_seconds,
        pool_recycle=settings.pool_recycle_seconds,
        # Probe pooled connections before use so a Postgres restart (common in
        # ephemeral dev environments) is transparently recovered instead of
        # surfacing a stale-connection error on the next query.
        pool_pre_ping=True,
        echo=settings.echo,
        future=True,
        connect_args=connect_args,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
