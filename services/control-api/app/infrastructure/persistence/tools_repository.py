from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.identifiers import TenantId, ToolId
from app.domain.tools.entities import Tool
from app.domain.tools.repository import ToolRepository
from app.infrastructure.persistence.models import ToolModel
from app.infrastructure.persistence.tools_mappers import model_to_tool, tool_to_model


class SqlAlchemyToolRepository(ToolRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tool: Tool) -> None:
        self._session.add(tool_to_model(tool))

    async def get(self, tenant_id: TenantId, tool_id: ToolId) -> Tool | None:
        model = await self._session.get(ToolModel, tool_id.value)
        if model is None or model.tenant_id != tenant_id.value:
            return None
        return model_to_tool(model)

    async def find_by_name(self, tenant_id: TenantId, name: str) -> Tool | None:
        stmt = select(ToolModel).where(
            ToolModel.tenant_id == tenant_id.value, ToolModel.name == name
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return model_to_tool(model) if model is not None else None

    async def list(self, tenant_id: TenantId) -> list[Tool]:
        stmt = (
            select(ToolModel)
            .where(ToolModel.tenant_id == tenant_id.value)
            .order_by(ToolModel.created_at)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [model_to_tool(m) for m in models]
