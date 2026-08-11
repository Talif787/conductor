from __future__ import annotations

from collections.abc import Callable

import structlog

from app.application.ports import UnitOfWork
from app.application.tools.commands import RegisterTool, UpdateTool
from app.application.tools.dtos import ToolDTO
from app.application.tools.mappers import to_tool_dto
from app.domain.shared.identifiers import TenantId, ToolId
from app.domain.tools.entities import Tool
from app.domain.tools.errors import ToolNameConflictError, ToolNotFoundError
from app.domain.tools.value_objects import ToolKind

logger = structlog.get_logger(__name__)

UnitOfWorkFactory = Callable[[], UnitOfWork]


class RegisterToolHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: RegisterTool) -> ToolDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        async with self._uow_factory() as uow:
            if await uow.tools.find_by_name(tenant_id, command.name.strip()) is not None:
                raise ToolNameConflictError(command.name.strip())
            tool = Tool.register(
                tenant_id=tenant_id,
                name=command.name,
                kind=ToolKind(command.kind),
                input_schema=command.input_schema,
                output_schema=command.output_schema,
                description=command.description,
                config=command.config,
            )
            await uow.tools.add(tool)
            await uow.commit()
        logger.info("tool.registered", tool_id=str(tool.id), tenant_id=str(tenant_id))
        return to_tool_dto(tool)


class UpdateToolHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: UpdateTool) -> ToolDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        tool_id = ToolId.parse(command.tool_id)
        async with self._uow_factory() as uow:
            tool = await uow.tools.get(tenant_id, tool_id)
            if tool is None:
                raise ToolNotFoundError(command.tool_id)
            tool.update(
                description=command.description,
                input_schema=command.input_schema,
                output_schema=command.output_schema,
                config=command.config,
            )
            await uow.commit()
        return to_tool_dto(tool)
