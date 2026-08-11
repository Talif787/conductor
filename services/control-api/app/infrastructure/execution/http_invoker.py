"""Invoke an HTTP tool: build a request from tool config and step context."""

from __future__ import annotations

from typing import Any

from app.application.execution.ports import ToolInvocation, ToolInvoker
from app.application.execution.tool_clients import HttpToolClient, HttpToolRequest
from app.domain.execution.errors import ToolExecutionError

_METHODS_WITH_BODY = {"POST", "PUT", "PATCH"}


class HttpToolInvoker(ToolInvoker):
    def __init__(self, client: HttpToolClient, default_timeout_seconds: int = 30) -> None:
        self._client = client
        self._default_timeout = default_timeout_seconds

    async def invoke(self, invocation: ToolInvocation) -> dict[str, Any]:
        config = invocation.tool.config
        url = config.get("url")
        if not url:
            raise ToolExecutionError(f"http tool '{invocation.tool.name}' is missing config.url")
        method = str(config.get("method", "POST")).upper()
        headers = {str(k): str(v) for k, v in config.get("headers", {}).items()}
        timeout = int(config.get("timeout_seconds", self._default_timeout))

        payload = {"parameters": invocation.parameters, "inputs": invocation.inputs}
        body = payload if method in _METHODS_WITH_BODY else None

        response = await self._client.send(
            HttpToolRequest(
                method=method,
                url=str(url),
                headers=headers,
                body=body,
                timeout_seconds=timeout,
            )
        )
        if response.status_code >= 400:
            raise ToolExecutionError(
                f"http tool '{invocation.tool.name}' returned status {response.status_code}"
            )
        if response.body is not None:
            return response.body
        return {"raw": response.text}
