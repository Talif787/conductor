"""HTTP endpoints for the Run resource."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import JSONResponse

from app.application.auth.principal import Principal
from app.application.execution.queries import GetRunExecution
from app.application.execution.query_handlers import GetRunExecutionHandler
from app.application.governance.command_handlers import SubmitRunHandler
from app.application.governance.commands import SubmitRun
from app.application.run.command_handlers import CancelRunHandler, CreateRunHandler
from app.application.run.commands import CancelRun, CreateRun
from app.application.run.queries import GetRun, ListRuns
from app.application.run.query_handlers import GetRunHandler, ListRunsHandler
from app.domain.identity.roles import Permission
from app.presentation.api.dependencies import (
    PageParams,
    provide_cancel_run_handler,
    provide_create_run_handler,
    provide_get_run_execution_handler,
    provide_get_run_handler,
    provide_list_runs_handler,
    provide_submit_run_handler,
    require_permission,
)
from app.presentation.api.v1.schemas import (
    ApprovalResponse,
    CreateRunRequest,
    PagedRunsResponse,
    RunExecutionResponse,
    RunResponse,
)

router = APIRouter(prefix="/runs", tags=["runs"])

_STATUS_PATTERN = "^(queued|planning|running|paused|awaiting_approval|completed|failed|cancelled)$"


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


@router.post("/{run_id}/execute", response_model=RunExecutionResponse)
async def execute_run(
    run_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_EXECUTE))],
    handler: Annotated[SubmitRunHandler, Depends(provide_submit_run_handler)],
) -> RunExecutionResponse | JSONResponse:
    result = await handler.handle(
        SubmitRun(
            tenant_id=str(principal.tenant_id),
            run_id=run_id,
            principal_id=str(principal.user_id),
            roles=tuple(role.value for role in principal.roles),
        )
    )
    if result.outcome == "pending_approval" and result.approval is not None:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=ApprovalResponse.from_dto(result.approval).model_dump(),
        )
    return RunExecutionResponse.from_dto(result.execution)


@router.get("/{run_id}/execution", response_model=RunExecutionResponse)
async def get_run_execution(
    run_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_READ))],
    handler: Annotated[GetRunExecutionHandler, Depends(provide_get_run_execution_handler)],
) -> RunExecutionResponse:
    dto = await handler.handle(GetRunExecution(tenant_id=str(principal.tenant_id), run_id=run_id))
    return RunExecutionResponse.from_dto(dto)
