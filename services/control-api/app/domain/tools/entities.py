"""Entities for the Tool Registry context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain.shared.identifiers import TenantId, ToolId
from app.domain.tools.value_objects import ToolKind


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Tool:
    id: ToolId
    tenant_id: TenantId
    name: str
    description: str
    kind: ToolKind
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def register(
        cls,
        *,
        tenant_id: TenantId,
        name: str,
        kind: ToolKind,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        description: str = "",
    ) -> Tool:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("tool name must not be empty")
        now = _utcnow()
        return cls(
            id=ToolId.new(),
            tenant_id=tenant_id,
            name=cleaned,
            description=description,
            kind=kind,
            input_schema=input_schema,
            output_schema=output_schema,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        description: str | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> None:
        if description is not None:
            self.description = description
        if input_schema is not None:
            self.input_schema = input_schema
        if output_schema is not None:
            self.output_schema = output_schema
        self.updated_at = _utcnow()
