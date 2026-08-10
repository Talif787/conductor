from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RegisterTool:
    tenant_id: str
    name: str
    kind: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    description: str = ""


@dataclass(frozen=True, slots=True)
class UpdateTool:
    tenant_id: str
    tool_id: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
