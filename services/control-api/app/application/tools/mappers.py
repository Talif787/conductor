from __future__ import annotations

from app.application.tools.dtos import ToolDTO
from app.domain.tools.entities import Tool


def to_tool_dto(tool: Tool) -> ToolDTO:
    return ToolDTO(
        id=str(tool.id),
        name=tool.name,
        description=tool.description,
        kind=tool.kind.value,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        created_at=tool.created_at.isoformat(),
        updated_at=tool.updated_at.isoformat(),
    )
