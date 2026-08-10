from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetTool:
    tenant_id: str
    tool_id: str


@dataclass(frozen=True, slots=True)
class ListTools:
    tenant_id: str
