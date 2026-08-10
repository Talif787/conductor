from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkflowVersionDTO:
    id: str
    workflow_id: str
    version: int
    status: str
    definition: dict[str, Any]
    created_at: str
    published_at: str | None


@dataclass(frozen=True, slots=True)
class WorkflowVersionSummaryDTO:
    version: int
    status: str
    published_at: str | None


@dataclass(frozen=True, slots=True)
class WorkflowDTO:
    id: str
    name: str
    description: str
    status: str
    created_at: str
    updated_at: str
    versions: list[WorkflowVersionSummaryDTO]
