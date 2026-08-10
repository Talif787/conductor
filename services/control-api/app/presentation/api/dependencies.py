"""FastAPI dependency providers (the composition root wiring)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, Query, Request

from app.application.ports import EventPublisher, UnitOfWork
from app.application.run.command_handlers import CancelRunHandler, CreateRunHandler
from app.application.run.query_handlers import GetRunHandler, ListRunsHandler
from app.config.settings import AppSettings, get_settings
from app.domain.run.value_objects import TenantId
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


def provide_settings() -> AppSettings:
    return get_settings()


def provide_uow_factory(request: Request) -> UnitOfWorkFactory:
    session_factory = request.app.state.session_factory

    def factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return factory


def provide_publisher(request: Request) -> EventPublisher:
    publisher: EventPublisher = request.app.state.publisher
    return publisher


def provide_create_run_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    publisher: Annotated[EventPublisher, Depends(provide_publisher)],
) -> CreateRunHandler:
    return CreateRunHandler(uow_factory, publisher)


def provide_cancel_run_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    publisher: Annotated[EventPublisher, Depends(provide_publisher)],
) -> CancelRunHandler:
    return CancelRunHandler(uow_factory, publisher)


def provide_get_run_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> GetRunHandler:
    return GetRunHandler(uow_factory)


def provide_list_runs_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> ListRunsHandler:
    return ListRunsHandler(uow_factory)


def get_current_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> TenantId:
    """Resolve the tenant for the request.

    Phase 1 seam: tenant identity comes from a header. Phase 2 replaces this
    single provider with JWT-derived tenancy without touching any handler.
    """
    if not x_tenant_id:
        raise ValueError("missing required X-Tenant-Id header")
    return TenantId.parse(x_tenant_id)


def get_page_params(
    settings: Annotated[AppSettings, Depends(provide_settings)],
    limit: Annotated[int | None, Query(ge=1)] = None,
    cursor: Annotated[str | None, Query()] = None,
) -> tuple[int, str | None]:
    effective = limit or settings.default_page_size
    return min(effective, settings.max_page_size), cursor


CurrentTenant = Annotated[TenantId, Depends(get_current_tenant)]
PageParams = Annotated[tuple[int, str | None], Depends(get_page_params)]
