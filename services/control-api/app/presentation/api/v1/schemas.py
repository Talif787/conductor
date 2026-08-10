"""Pydantic request and response models for the v1 HTTP API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.application.run.dtos import PagedRunsDTO, RunDTO, RunSummaryDTO


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=8000)
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")
    parameters: dict[str, Any] = Field(default_factory=dict)
    workflow_id: str | None = Field(default=None, max_length=64)
    workflow_version: str | None = Field(default=None, max_length=32)


class RunResponse(BaseModel):
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

    @classmethod
    def from_dto(cls, dto: RunDTO) -> RunResponse:
        return cls(**asdict(dto))


class RunSummaryResponse(BaseModel):
    id: str
    goal: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: RunSummaryDTO) -> RunSummaryResponse:
        return cls(**asdict(dto))


class PagedRunsResponse(BaseModel):
    items: list[RunSummaryResponse]
    next_cursor: str | None

    @classmethod
    def from_dto(cls, dto: PagedRunsDTO) -> PagedRunsResponse:
        return cls(
            items=[RunSummaryResponse.from_dto(item) for item in dto.items],
            next_cursor=dto.next_cursor,
        )


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
