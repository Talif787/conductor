"""HTTP endpoints for the Tool Registry."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.application.auth.principal import Principal
from app.application.tools.command_handlers import RegisterToolHandler, UpdateToolHandler
from app.application.tools.commands import RegisterTool, UpdateTool
from app.application.tools.queries import GetTool, ListTools
from app.application.tools.query_handlers import GetToolHandler, ListToolsHandler
from app.domain.identity.roles import Permission
from app.presentation.api.dependencies import (
    provide_get_tool_handler,
    provide_list_tools_handler,
    provide_register_tool_handler,
    provide_update_tool_handler,
    require_permission,
)
from app.presentation.api.v1.schemas import (
    RegisterToolRequest,
    ToolResponse,
    UpdateToolRequest,
)

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def register_tool(
    body: RegisterToolRequest,
    principal: Annotated[Principal, Depends(require_permission(Permission.TOOLS_WRITE))],
    handler: Annotated[RegisterToolHandler, Depends(provide_register_tool_handler)],
) -> ToolResponse:
    dto = await handler.handle(
        RegisterTool(
            tenant_id=str(principal.tenant_id),
            name=body.name,
            kind=body.kind,
            input_schema=body.input_schema,
            output_schema=body.output_schema,
            description=body.description,
            config=body.config,
        )
    )
    return ToolResponse.from_dto(dto)


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    principal: Annotated[Principal, Depends(require_permission(Permission.TOOLS_READ))],
    handler: Annotated[ListToolsHandler, Depends(provide_list_tools_handler)],
) -> list[ToolResponse]:
    dtos = await handler.handle(ListTools(tenant_id=str(principal.tenant_id)))
    return [ToolResponse.from_dto(dto) for dto in dtos]


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.TOOLS_READ))],
    handler: Annotated[GetToolHandler, Depends(provide_get_tool_handler)],
) -> ToolResponse:
    dto = await handler.handle(GetTool(tenant_id=str(principal.tenant_id), tool_id=tool_id))
    return ToolResponse.from_dto(dto)


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    body: UpdateToolRequest,
    principal: Annotated[Principal, Depends(require_permission(Permission.TOOLS_WRITE))],
    handler: Annotated[UpdateToolHandler, Depends(provide_update_tool_handler)],
) -> ToolResponse:
    dto = await handler.handle(
        UpdateTool(
            tenant_id=str(principal.tenant_id),
            tool_id=tool_id,
            description=body.description,
            input_schema=body.input_schema,
            output_schema=body.output_schema,
            config=body.config,
        )
    )
    return ToolResponse.from_dto(dto)
