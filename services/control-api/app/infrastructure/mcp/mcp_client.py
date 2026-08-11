"""A minimal MCP client over the streamable HTTP transport.

Performs the initialize handshake, sends the initialized notification, then
calls tools/call. This targets MCP servers that speak JSON-RPC over HTTP and
respond with JSON or a single SSE data frame. The stdio transport and richer
capability negotiation are future work. Exercised against a live MCP server.
"""

from __future__ import annotations

import json
from typing import Any

from app.application.execution.tool_clients import (
    McpToolClient,
    McpToolRequest,
    McpToolResponse,
)
from app.domain.execution.errors import ToolExecutionError

_PROTOCOL_VERSION = "2025-06-18"


class JsonRpcMcpToolClient(McpToolClient):
    def __init__(self, client_name: str = "conductor", client_version: str = "0.5.0") -> None:
        self._client_name = client_name
        self._client_version = client_version

    async def call_tool(self, request: McpToolRequest) -> McpToolResponse:
        import httpx  # lazy import so the module loads without httpx present

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **request.headers,
        }
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                init = await self._post(
                    client,
                    request.server_url,
                    headers,
                    self._rpc(1, "initialize", self._init_params()),
                )
                session = init.headers.get("Mcp-Session-Id")
                if session:
                    headers["Mcp-Session-Id"] = session
                await self._post(
                    client,
                    request.server_url,
                    headers,
                    self._notification("notifications/initialized"),
                )
                result = await self._post(
                    client,
                    request.server_url,
                    headers,
                    self._rpc(
                        2,
                        "tools/call",
                        {"name": request.tool_name, "arguments": request.arguments},
                    ),
                )
        except httpx.HTTPError as exc:
            raise ToolExecutionError(f"mcp request failed: {exc}") from exc

        envelope = self._decode(result)
        if "error" in envelope:
            return McpToolResponse(content={"error": envelope["error"]}, is_error=True)
        payload = envelope.get("result", {})
        return McpToolResponse(content=payload, is_error=bool(payload.get("isError", False)))

    def _init_params(self) -> dict[str, Any]:
        return {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": self._client_name, "version": self._client_version},
        }

    def _rpc(self, request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}

    def _notification(self, method: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "method": method}

    async def _post(self, client: Any, url: str, headers: dict[str, str], payload: dict) -> Any:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response

    def _decode(self, response: Any) -> dict[str, Any]:
        content_type = response.headers.get("Content-Type", "")
        text = response.text
        if "text/event-stream" in content_type:
            for line in text.splitlines():
                if line.startswith("data:"):
                    text = line[len("data:") :].strip()
        if not text:
            return {}
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(f"invalid mcp response: {exc}") from exc
        return decoded if isinstance(decoded, dict) else {"result": decoded}
