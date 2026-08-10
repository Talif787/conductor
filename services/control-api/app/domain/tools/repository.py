"""Repository port for the Tool Registry context."""

from __future__ import annotations

import abc

from app.domain.shared.identifiers import TenantId, ToolId
from app.domain.tools.entities import Tool


class ToolRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, tool: Tool) -> None: ...

    @abc.abstractmethod
    async def get(self, tenant_id: TenantId, tool_id: ToolId) -> Tool | None: ...

    @abc.abstractmethod
    async def find_by_name(self, tenant_id: TenantId, name: str) -> Tool | None: ...

    @abc.abstractmethod
    async def list(self, tenant_id: TenantId) -> list[Tool]: ...
