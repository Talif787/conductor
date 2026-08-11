from __future__ import annotations

import pytest

from app.application.execution.ports import ToolInvocation, ToolInvoker
from app.domain.execution.errors import ToolKindNotSupportedError
from app.domain.shared.identifiers import TenantId
from app.domain.tools.entities import Tool
from app.domain.tools.value_objects import ToolKind
from app.infrastructure.execution.tool_invoker import BuiltinToolInvoker, CompositeToolInvoker
from app.infrastructure.llm.gateway import FakeLLMGateway


def _tool(name: str, kind: ToolKind) -> Tool:
    return Tool.register(
        tenant_id=TenantId.new(), name=name, kind=kind, input_schema={}, output_schema={}
    )


class _Marker(ToolInvoker):
    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def invoke(self, invocation: ToolInvocation) -> dict:
        return {"routed": self.tag}


async def test_routes_each_kind_to_its_invoker() -> None:
    invoker = CompositeToolInvoker(
        builtin=BuiltinToolInvoker(FakeLLMGateway()),
        http=_Marker("http"),
        mcp=_Marker("mcp"),
    )
    builtin_out = await invoker.invoke(
        ToolInvocation(_tool("echo", ToolKind.BUILTIN), {"a": 1}, {})
    )
    assert builtin_out["parameters"] == {"a": 1}
    http_out = await invoker.invoke(ToolInvocation(_tool("h", ToolKind.HTTP), {}, {}))
    assert http_out == {"routed": "http"}
    mcp_out = await invoker.invoke(ToolInvocation(_tool("m", ToolKind.MCP), {}, {}))
    assert mcp_out == {"routed": "mcp"}


async def test_builtin_only_composite_defers_http_and_mcp() -> None:
    invoker = CompositeToolInvoker(BuiltinToolInvoker(FakeLLMGateway()))
    with pytest.raises(ToolKindNotSupportedError):
        await invoker.invoke(ToolInvocation(_tool("h", ToolKind.HTTP), {}, {}))
    with pytest.raises(ToolKindNotSupportedError):
        await invoker.invoke(ToolInvocation(_tool("m", ToolKind.MCP), {}, {}))
