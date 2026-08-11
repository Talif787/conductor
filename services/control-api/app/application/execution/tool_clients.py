"""Transport ports for external tool invocation.

The invoker logic (config to request, response to output, error handling) sits
behind these ports so it can be tested with fakes. Real adapters (httpx for
HTTP, a JSON-RPC client for MCP) live in infrastructure.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class HttpToolRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None
    timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class HttpToolResponse:
    status_code: int
    body: dict[str, Any] | None
    text: str


class HttpToolClient(abc.ABC):
    @abc.abstractmethod
    async def send(self, request: HttpToolRequest) -> HttpToolResponse: ...


@dataclass(frozen=True, slots=True)
class McpToolRequest:
    server_url: str
    tool_name: str
    arguments: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class McpToolResponse:
    content: dict[str, Any]
    is_error: bool = False


class McpToolClient(abc.ABC):
    @abc.abstractmethod
    async def call_tool(self, request: McpToolRequest) -> McpToolResponse: ...
