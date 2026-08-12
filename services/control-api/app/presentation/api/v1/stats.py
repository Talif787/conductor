"""HTTP endpoints for the CQRS read model: run statistics and recent views."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.auth.principal import Principal
from app.application.projections.queries import GetRunStats, ListRunViews
from app.application.projections.query_handlers import (
    GetRunStatsHandler,
    ListRunViewsHandler,
)
from app.domain.identity.roles import Permission
from app.presentation.api.dependencies import (
    provide_get_run_stats_handler,
    provide_list_run_views_handler,
    require_permission,
)
from app.presentation.api.v1.schemas import RunStatsResponse, RunViewResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/runs", response_model=RunStatsResponse)
async def run_stats(
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_READ))],
    handler: Annotated[GetRunStatsHandler, Depends(provide_get_run_stats_handler)],
) -> RunStatsResponse:
    dto = await handler.handle(GetRunStats(tenant_id=str(principal.tenant_id)))
    return RunStatsResponse.from_dto(dto)


@router.get("/runs/recent", response_model=list[RunViewResponse])
async def recent_run_views(
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_READ))],
    handler: Annotated[ListRunViewsHandler, Depends(provide_list_run_views_handler)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RunViewResponse]:
    dtos = await handler.handle(ListRunViews(tenant_id=str(principal.tenant_id), limit=limit))
    return [RunViewResponse.from_dto(dto) for dto in dtos]
