"""Value objects for the Tool Registry context."""

from __future__ import annotations

from enum import StrEnum


class ToolKind(StrEnum):
    BUILTIN = "builtin"
    HTTP = "http"
    MCP = "mcp"
