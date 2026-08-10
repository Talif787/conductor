"""Framework-free data transfer objects returned by the application layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class RunDTO:
    id: str
    tenant_id: str
    goal: str
    status: str
    priority: str
    parameters: dict[str, Any]
    workflow_id: str | None
    workflow_version: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RunSummaryDTO:
    id: str
    goal: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PagedRunsDTO:
    items: list[RunSummaryDTO]
    next_cursor: str | None
