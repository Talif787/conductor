from __future__ import annotations

import pytest

from app.application.execution.ports import ToolInvocation
from app.application.execution.tool_clients import (
    McpToolClient,
    McpToolRequest,
    McpToolResponse,
)
from app.domain.execution.errors import ToolExecutionError
from app.domain.shared.identifiers import TenantId
from app.domain.tools.entities import Tool
from app.domain.tools.value_objects import ToolKind
from app.infrastructure.execution.mcp_invoker import McpToolInvoker


def _mcp_tool(name: str, config: dict) -> Tool:
    return Tool.register(
        tenant_id=TenantId.new(),
        name=name,
        kind=ToolKind.MCP,
        input_schema={},
        output_schema={},
        config=config,
    )


class _FakeMcpClient(McpToolClient):
    def __init__(self, response: McpToolResponse) -> None:
        self.response = response
        self.seen: McpToolRequest | None = None

    async def call_tool(self, request: McpToolRequest) -> McpToolResponse:
        self.seen = request
        return self.response


async def test_success_threads_tool_name_and_arguments() -> None:
    client = _FakeMcpClient(McpToolResponse({"content": [{"type": "text", "text": "done"}]}))
    invoker = McpToolInvoker(client)
    config = {"server_url": "https://mcp.example.com/", "tool": "web_search"}
    out = await invoker.invoke(ToolInvocation(_mcp_tool("search", config), {"q": "x"}, {}))
    assert out["content"][0]["text"] == "done"
    assert client.seen is not None
    assert client.seen.tool_name == "web_search"
    assert client.seen.arguments == {"parameters": {"q": "x"}, "inputs": {}}


async def test_tool_name_defaults_to_registry_name() -> None:
    client = _FakeMcpClient(McpToolResponse({"content": []}))
    invoker = McpToolInvoker(client)
    await invoker.invoke(ToolInvocation(_mcp_tool("my_tool", {"server_url": "https://m"}), {}, {}))
    assert client.seen is not None
    assert client.seen.tool_name == "my_tool"


async def test_missing_server_url_raises() -> None:
    invoker = McpToolInvoker(_FakeMcpClient(McpToolResponse({})))
    with pytest.raises(ToolExecutionError, match="server_url"):
        await invoker.invoke(ToolInvocation(_mcp_tool("t", {}), {}, {}))


async def test_error_result_raises() -> None:
    client = _FakeMcpClient(McpToolResponse({"isError": True}, is_error=True))
    invoker = McpToolInvoker(client)
    with pytest.raises(ToolExecutionError):
        await invoker.invoke(ToolInvocation(_mcp_tool("t", {"server_url": "https://m"}), {}, {}))
