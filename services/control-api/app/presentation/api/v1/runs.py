"""HTTP endpoints for the Run resource."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.application.auth.principal import Principal
from app.application.run.command_handlers import CancelRunHandler, CreateRunHandler
from app.application.run.commands import CancelRun, CreateRun
from app.application.run.queries import GetRun, ListRuns
from app.application.run.query_handlers import GetRunHandler, ListRunsHandler
from app.domain.identity.roles import Permission
from app.presentation.api.dependencies import (
    PageParams,
    provide_cancel_run_handler,
    provide_create_run_handler,
    provide_get_run_handler,
    provide_list_runs_handler,
    require_permission,
)
from app.presentation.api.v1.schemas import CreateRunRequest, PagedRunsResponse, RunResponse

router = APIRouter(prefix="/runs", tags=["runs"])

_STATUS_PATTERN = "^(queued|planning|running|paused|completed|failed|cancelled)$"


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    body: CreateRunRequest,
    response: Response,
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_CREATE))],
    handler: Annotated[CreateRunHandler, Depends(provide_create_run_handler)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RunResponse:
    command = CreateRun(
        tenant_id=str(principal.tenant_id),
        goal=body.goal,
        priority=body.priority,
        parameters=body.parameters,
        workflow_id=body.workflow_id,
        workflow_version=body.workflow_version,
        idempotency_key=idempotency_key,
    )
    dto = await handler.handle(command)
    response.headers["Location"] = f"/api/v1/runs/{dto.id}"
    return RunResponse.from_dto(dto)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_READ))],
    handler: Annotated[GetRunHandler, Depends(provide_get_run_handler)],
) -> RunResponse:
    dto = await handler.handle(GetRun(tenant_id=str(principal.tenant_id), run_id=run_id))
    return RunResponse.from_dto(dto)


@router.get("", response_model=PagedRunsResponse)
async def list_runs(
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_READ))],
    page: PageParams,
    handler: Annotated[ListRunsHandler, Depends(provide_list_runs_handler)],
    run_status: Annotated[str | None, Query(alias="status", pattern=_STATUS_PATTERN)] = None,
) -> PagedRunsResponse:
    limit, cursor = page
    dto = await handler.handle(
        ListRuns(tenant_id=str(principal.tenant_id), status=run_status, limit=limit, cursor=cursor)
    )
    return PagedRunsResponse.from_dto(dto)


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_CANCEL))],
    handler: Annotated[CancelRunHandler, Depends(provide_cancel_run_handler)],
) -> RunResponse:
    dto = await handler.handle(CancelRun(tenant_id=str(principal.tenant_id), run_id=run_id))
    return RunResponse.from_dto(dto)
