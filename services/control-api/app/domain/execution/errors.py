"""Errors for the Execution context."""

from __future__ import annotations


class ExecutionError(Exception):
    """Base class for execution failures."""


class RunNotExecutableError(ExecutionError):
    """The run cannot be executed in its current state or configuration."""


class RunExecutionNotFoundError(ExecutionError):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"no execution found for run '{run_id}'")


class ToolExecutionError(ExecutionError):
    """A tool failed while running a step."""


class ToolKindNotSupportedError(ExecutionError):
    def __init__(self, kind: str) -> None:
        super().__init__(
            f"tool kind '{kind}' is not executable by the local engine yet; "
            "http and mcp invokers arrive with durable orchestration"
        )
        self.kind = kind


class BuiltinNotFoundError(ExecutionError):
    def __init__(self, name: str) -> None:
        super().__init__(f"no builtin handler named '{name}'")
        self.name = name


class LLMError(ExecutionError):
    """The LLM gateway failed to produce a completion."""
