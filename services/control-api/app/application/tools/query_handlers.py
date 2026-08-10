from __future__ import annotations

from collections.abc import Callable

from app.application.ports import UnitOfWork
from app.application.tools.dtos import ToolDTO
from app.application.tools.mappers import to_tool_dto
from app.application.tools.queries import GetTool, ListTools
from app.domain.shared.identifiers import TenantId, ToolId
from app.domain.tools.errors import ToolNotFoundError

UnitOfWorkFactory = Callable[[], UnitOfWork]


class GetToolHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: GetTool) -> ToolDTO:
        tenant_id = TenantId.parse(query.tenant_id)
        tool_id = ToolId.parse(query.tool_id)
        async with self._uow_factory() as uow:
            tool = await uow.tools.get(tenant_id, tool_id)
            if tool is None:
                raise ToolNotFoundError(query.tool_id)
            return to_tool_dto(tool)


class ListToolsHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: ListTools) -> list[ToolDTO]:
        tenant_id = TenantId.parse(query.tenant_id)
        async with self._uow_factory() as uow:
            tools = await uow.tools.list(tenant_id)
            return [to_tool_dto(tool) for tool in tools]
