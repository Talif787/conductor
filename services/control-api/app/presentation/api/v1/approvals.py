"""HTTP endpoints for human-in-the-loop approval requests."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.auth.principal import Principal
from app.application.governance.command_handlers import (
    ApproveRequestHandler,
    RejectRequestHandler,
)
from app.application.governance.commands import ApproveRequest, RejectRequest
from app.application.governance.queries import GetApproval, ListApprovals
from app.application.governance.query_handlers import (
    GetApprovalHandler,
    ListApprovalsHandler,
)
from app.domain.identity.roles import Permission
from app.presentation.api.dependencies import (
    provide_approve_request_handler,
    provide_get_approval_handler,
    provide_list_approvals_handler,
    provide_reject_request_handler,
    require_permission,
)
from app.presentation.api.v1.schemas import (
    ApprovalDecisionRequest,
    ApprovalResponse,
    RunExecutionResponse,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])

_STATUS_PATTERN = "^(pending|approved|rejected)$"


@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_READ))],
    handler: Annotated[ListApprovalsHandler, Depends(provide_list_approvals_handler)],
    status: Annotated[str | None, Query(pattern=_STATUS_PATTERN)] = None,
) -> list[ApprovalResponse]:
    dtos = await handler.handle(ListApprovals(tenant_id=str(principal.tenant_id), status=status))
    return [ApprovalResponse.from_dto(dto) for dto in dtos]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_READ))],
    handler: Annotated[GetApprovalHandler, Depends(provide_get_approval_handler)],
) -> ApprovalResponse:
    dto = await handler.handle(
        GetApproval(tenant_id=str(principal.tenant_id), approval_id=approval_id)
    )
    return ApprovalResponse.from_dto(dto)


@router.post("/{approval_id}/approve", response_model=RunExecutionResponse)
async def approve_request(
    approval_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_APPROVE))],
    handler: Annotated[ApproveRequestHandler, Depends(provide_approve_request_handler)],
    body: ApprovalDecisionRequest | None = None,
) -> RunExecutionResponse:
    result = await handler.handle(
        ApproveRequest(
            tenant_id=str(principal.tenant_id),
            approval_id=approval_id,
            decided_by=str(principal.user_id),
            note=body.note if body else None,
        )
    )
    return RunExecutionResponse.from_dto(result.execution)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.RUNS_APPROVE))],
    handler: Annotated[RejectRequestHandler, Depends(provide_reject_request_handler)],
    body: ApprovalDecisionRequest | None = None,
) -> ApprovalResponse:
    dto = await handler.handle(
        RejectRequest(
            tenant_id=str(principal.tenant_id),
            approval_id=approval_id,
            decided_by=str(principal.user_id),
            note=body.note if body else None,
        )
    )
    return ApprovalResponse.from_dto(dto)
