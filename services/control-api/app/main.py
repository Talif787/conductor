"""Application factory and ASGI entry point for the Conductor Control API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.application.projections.run_view import RunViewProjector
from app.config.settings import AppSettings, get_settings
from app.infrastructure.eventing.relay import OutboxRelay, build_event_bus
from app.infrastructure.messaging.publisher import LoggingEventPublisher
from app.infrastructure.observability.logging import configure_logging
from app.infrastructure.observability.tracing import configure_tracing
from app.infrastructure.persistence.session import create_engine, create_session_factory
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.password import Argon2PasswordHasher
from app.infrastructure.security.tokens import JwtAccessTokenService
from app.presentation.api.errors import register_exception_handlers
from app.presentation.api.middleware import ObservabilityMiddleware
from app.presentation.api.v1.approvals import router as approvals_router
from app.presentation.api.v1.auth import router as auth_router
from app.presentation.api.v1.health import router as health_router
from app.presentation.api.v1.members import router as members_router
from app.presentation.api.v1.runs import router as runs_router
from app.presentation.api.v1.stats import router as stats_router
from app.presentation.api.v1.tools import router as tools_router
from app.presentation.api.v1.workflows import router as workflows_router


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database)
        session_factory = create_session_factory(engine)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.publisher = LoggingEventPublisher()
        app.state.password_hasher = Argon2PasswordHasher()
        app.state.token_service = JwtAccessTokenService(
            secret=settings.auth.secret,
            issuer=settings.auth.issuer,
            audience=settings.auth.audience,
            ttl_seconds=settings.auth.access_ttl_seconds,
            algorithm=settings.auth.algorithm,
        )
        configure_tracing(settings.observability, app, engine)

        # Optional in-process outbox relay: drains the read model while the web
        # process is awake. Enabled on sleep-on-idle free hosting where a
        # separate always-on worker is not free. Requires WEB_CONCURRENCY=1.
        relay_task: asyncio.Task[None] | None = None
        relay_stop: asyncio.Event | None = None
        if settings.events.relay_inprocess:
            relay_stop = asyncio.Event()
            relay = OutboxRelay(
                lambda: SqlAlchemyUnitOfWork(session_factory),
                build_event_bus(settings.events),
                RunViewProjector(),
                batch_size=settings.events.relay_batch_size,
                poll_interval=settings.events.relay_poll_interval_seconds,
            )
            relay_task = asyncio.create_task(relay.run(stop=relay_stop))

        try:
            yield
        finally:
            if relay_stop is not None:
                relay_stop.set()
            if relay_task is not None:
                relay_task.cancel()
                with suppress(asyncio.CancelledError):
                    await relay_task
            await engine.dispose()

    app = FastAPI(
        title="Conductor Control API",
        version="1.0.0",
        summary="Control plane for the Agentic AI Workflow Automation Platform.",
        lifespan=lifespan,
    )

    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(runs_router, prefix=settings.api_prefix)
    app.include_router(approvals_router, prefix=settings.api_prefix)
    app.include_router(stats_router, prefix=settings.api_prefix)
    app.include_router(tools_router, prefix=settings.api_prefix)
    app.include_router(workflows_router, prefix=settings.api_prefix)
    app.include_router(members_router, prefix=settings.api_prefix)
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
