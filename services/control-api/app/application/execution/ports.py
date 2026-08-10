"""Ports for executing a workflow: tool invocation, LLM access, engine."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from app.domain.execution.entities import RunExecution
from app.domain.run.entities import Run
from app.domain.tools.entities import Tool
from app.domain.workflows.value_objects import WorkflowDefinition


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """Everything a tool needs to run one step."""

    tool: Tool
    parameters: dict[str, Any]
    inputs: dict[str, dict[str, Any]]


class ToolInvoker(abc.ABC):
    @abc.abstractmethod
    async def invoke(self, invocation: ToolInvocation) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class LLMRequest:
    prompt: str
    model: str
    max_tokens: int = 512
    temperature: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMGateway(abc.ABC):
    @abc.abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse: ...


class ExecutionEngine(abc.ABC):
    @abc.abstractmethod
    async def execute(
        self,
        run: Run,
        definition: WorkflowDefinition,
        tools: dict[str, Tool],
    ) -> RunExecution: ...
