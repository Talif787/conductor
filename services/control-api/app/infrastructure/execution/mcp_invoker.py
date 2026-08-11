"""Invoke an MCP tool: call tools/call on a configured MCP server."""

from __future__ import annotations

from typing import Any

from app.application.execution.ports import ToolInvocation, ToolInvoker
from app.application.execution.tool_clients import McpToolClient, McpToolRequest
from app.domain.execution.errors import ToolExecutionError


class McpToolInvoker(ToolInvoker):
    def __init__(self, client: McpToolClient, default_timeout_seconds: int = 30) -> None:
        self._client = client
        self._default_timeout = default_timeout_seconds

    async def invoke(self, invocation: ToolInvocation) -> dict[str, Any]:
        config = invocation.tool.config
        server_url = config.get("server_url")
        if not server_url:
            raise ToolExecutionError(
                f"mcp tool '{invocation.tool.name}' is missing config.server_url"
            )
        remote_tool = str(config.get("tool", invocation.tool.name))
        headers = {str(k): str(v) for k, v in config.get("headers", {}).items()}
        timeout = int(config.get("timeout_seconds", self._default_timeout))

        arguments = {"parameters": invocation.parameters, "inputs": invocation.inputs}
        response = await self._client.call_tool(
            McpToolRequest(
                server_url=str(server_url),
                tool_name=remote_tool,
                arguments=arguments,
                headers=headers,
                timeout_seconds=timeout,
            )
        )
        if response.is_error:
            raise ToolExecutionError(
                f"mcp tool '{invocation.tool.name}' reported an error: {response.content}"
            )
        return response.content
