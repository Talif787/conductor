from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolDTO:
    id: str
    name: str
    description: str
    kind: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    created_at: str
    updated_at: str
