from __future__ import annotations

import pytest

from app.application.execution.ports import ToolInvocation
from app.application.execution.tool_clients import (
    HttpToolClient,
    HttpToolRequest,
    HttpToolResponse,
)
from app.domain.execution.errors import ToolExecutionError
from app.domain.shared.identifiers import TenantId
from app.domain.tools.entities import Tool
from app.domain.tools.value_objects import ToolKind
from app.infrastructure.execution.http_invoker import HttpToolInvoker


def _http_tool(config: dict) -> Tool:
    return Tool.register(
        tenant_id=TenantId.new(),
        name="fetch",
        kind=ToolKind.HTTP,
        input_schema={},
        output_schema={},
        config=config,
    )


class _FakeHttpClient(HttpToolClient):
    def __init__(self, response: HttpToolResponse) -> None:
        self.response = response
        self.seen: HttpToolRequest | None = None

    async def send(self, request: HttpToolRequest) -> HttpToolResponse:
        self.seen = request
        return self.response


async def test_post_threads_body_and_headers_and_returns_json() -> None:
    client = _FakeHttpClient(HttpToolResponse(200, {"ok": True, "value": 42}, ""))
    invoker = HttpToolInvoker(client)
    config = {"url": "https://api.example.com/echo", "method": "post", "headers": {"X-Key": "a"}}
    out = await invoker.invoke(
        ToolInvocation(_http_tool(config), {"city": "boston"}, {"prev": {"t": 1}})
    )
    assert out == {"ok": True, "value": 42}
    assert client.seen is not None
    assert client.seen.method == "POST"
    assert client.seen.url == "https://api.example.com/echo"
    assert client.seen.headers == {"X-Key": "a"}
    assert client.seen.body == {"parameters": {"city": "boston"}, "inputs": {"prev": {"t": 1}}}


async def test_get_sends_no_body() -> None:
    client = _FakeHttpClient(HttpToolResponse(200, {"g": 1}, ""))
    invoker = HttpToolInvoker(client)
    await invoker.invoke(ToolInvocation(_http_tool({"url": "https://x", "method": "GET"}), {}, {}))
    assert client.seen is not None
    assert client.seen.method == "GET"
    assert client.seen.body is None


async def test_missing_url_raises() -> None:
    invoker = HttpToolInvoker(_FakeHttpClient(HttpToolResponse(200, {}, "")))
    with pytest.raises(ToolExecutionError, match="config.url"):
        await invoker.invoke(ToolInvocation(_http_tool({}), {}, {}))


async def test_error_status_raises() -> None:
    invoker = HttpToolInvoker(_FakeHttpClient(HttpToolResponse(503, None, "down")))
    with pytest.raises(ToolExecutionError, match="503"):
        await invoker.invoke(ToolInvocation(_http_tool({"url": "https://x"}), {}, {}))


async def test_non_json_body_returns_raw_text() -> None:
    invoker = HttpToolInvoker(_FakeHttpClient(HttpToolResponse(200, None, "plain text")))
    out = await invoker.invoke(ToolInvocation(_http_tool({"url": "https://x"}), {}, {}))
    assert out == {"raw": "plain text"}
