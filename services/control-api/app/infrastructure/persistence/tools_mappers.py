from __future__ import annotations

from app.domain.shared.identifiers import TenantId, ToolId
from app.domain.tools.entities import Tool
from app.domain.tools.value_objects import ToolKind
from app.infrastructure.persistence.models import ToolModel


def tool_to_model(tool: Tool) -> ToolModel:
    return ToolModel(
        id=tool.id.value,
        tenant_id=tool.tenant_id.value,
        name=tool.name,
        description=tool.description,
        kind=tool.kind.value,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
    )


def model_to_tool(model: ToolModel) -> Tool:
    return Tool(
        id=ToolId(model.id),
        tenant_id=TenantId(model.tenant_id),
        name=model.name,
        description=model.description,
        kind=ToolKind(model.kind),
        input_schema=model.input_schema,
        output_schema=model.output_schema,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
