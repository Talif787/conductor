"""Errors for the Tool Registry context."""

from __future__ import annotations


class ToolError(Exception):
    """Base class for tool registry failures."""


class ToolNotFoundError(ToolError):
    def __init__(self, tool_id: str) -> None:
        super().__init__(f"tool '{tool_id}' was not found")


class ToolNameConflictError(ToolError):
    def __init__(self, name: str) -> None:
        super().__init__(f"a tool named '{name}' already exists")
        self.name = name
