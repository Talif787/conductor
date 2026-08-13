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


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class PrincipalResponse(BaseModel):
    user_id: str
    tenant_id: str
    roles: list[str]
    permissions: list[str]


class RegisterToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(builtin|http|mcp)$")
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    description: str = Field(default="", max_length=2000)
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=2000)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class ToolResponse(BaseModel):
    id: str
    name: str
    description: str
    kind: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    config: dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_dto(cls, dto: Any) -> ToolResponse:
        return cls(**asdict(dto))


class StepSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1, max_length=128)
    name: str = Field(default="", max_length=200)
    tool_id: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)


class WorkflowDefinitionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[StepSchema] = Field(default_factory=list)


class CreateWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class UpdateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition: WorkflowDefinitionSchema


class WorkflowVersionResponse(BaseModel):
    id: str
    workflow_id: str
    version: int
    status: str
    definition: dict[str, Any]
    created_at: str
    published_at: str | None

    @classmethod
    def from_dto(cls, dto: Any) -> WorkflowVersionResponse:
        return cls(**asdict(dto))


class WorkflowVersionSummary(BaseModel):
    version: int
    status: str
    published_at: str | None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    created_at: str
    updated_at: str
    versions: list[WorkflowVersionSummary]

    @classmethod
    def from_dto(cls, dto: Any) -> WorkflowResponse:
        return cls(
            id=dto.id,
            name=dto.name,
            description=dto.description,
            status=dto.status,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
            versions=[WorkflowVersionSummary(**asdict(v)) for v in dto.versions],
        )


class StepExecutionResponse(BaseModel):
    step_id: str
    tool_id: str
    position: int
    status: str
    output: dict[str, Any] | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    cost_usd: float


class RunExecutionResponse(BaseModel):
    run_id: str
    status: str
    error: str | None
    started_at: str
    finished_at: str | None
    total_cost_usd: float
    steps: list[StepExecutionResponse]

    @classmethod
    def from_dto(cls, dto: Any) -> RunExecutionResponse:
        return cls(
            run_id=dto.run_id,
            status=dto.status,
            error=dto.error,
            started_at=dto.started_at,
            finished_at=dto.finished_at,
            total_cost_usd=dto.total_cost_usd,
            steps=[StepExecutionResponse(**asdict(s)) for s in dto.steps],
        )


class ApprovalResponse(BaseModel):
    id: str
    run_id: str
    reason: str
    status: str
    requested_at: str
    decided_at: str | None
    decided_by: str | None
    decision_note: str | None

    @classmethod
    def from_dto(cls, dto: Any) -> ApprovalResponse:
        return cls(**asdict(dto))


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = None


class RunStatsResponse(BaseModel):
    total: int
    active: int
    by_status: dict[str, int]

    @classmethod
    def from_dto(cls, dto: Any) -> RunStatsResponse:
        return cls(**asdict(dto))


class RunViewResponse(BaseModel):
    run_id: str
    tenant_id: str
    status: str
    goal: str
    priority: str
    created_at: str
    updated_at: str
    event_count: int

    @classmethod
    def from_dto(cls, dto: Any) -> RunViewResponse:
        return cls(**asdict(dto))


class MemberResponse(BaseModel):
    user_id: str
    email: str
    roles: list[str]

    @classmethod
    def from_dto(cls, dto: Any) -> MemberResponse:
        return cls(**asdict(dto))
