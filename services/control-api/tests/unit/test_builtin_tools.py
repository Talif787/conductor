from __future__ import annotations

import pytest

from app.application.execution.ports import ToolInvocation
from app.domain.execution.errors import BuiltinNotFoundError, ToolKindNotSupportedError
from app.domain.shared.identifiers import TenantId
from app.domain.tools.entities import Tool
from app.domain.tools.value_objects import ToolKind
from app.infrastructure.execution.tool_invoker import BuiltinToolInvoker, CompositeToolInvoker
from app.infrastructure.llm.gateway import FakeLLMGateway


def _tool(name: str, kind: ToolKind = ToolKind.BUILTIN) -> Tool:
    return Tool.register(
        tenant_id=TenantId.new(), name=name, kind=kind, input_schema={}, output_schema={}
    )


@pytest.fixture
def invoker() -> CompositeToolInvoker:
    return CompositeToolInvoker(BuiltinToolInvoker(FakeLLMGateway()))


async def test_echo_returns_parameters_and_inputs(invoker) -> None:
    out = await invoker.invoke(ToolInvocation(_tool("echo"), {"text": "hi"}, {"up": {"x": 1}}))
    assert out["parameters"] == {"text": "hi"}
    assert out["inputs"] == {"up": {"x": 1}}


async def test_uppercase_from_parameters(invoker) -> None:
    out = await invoker.invoke(ToolInvocation(_tool("uppercase"), {"text": "hello"}, {}))
    assert out["text"] == "HELLO"


async def test_uppercase_falls_back_to_upstream(invoker) -> None:
    out = await invoker.invoke(ToolInvocation(_tool("uppercase"), {}, {"prev": {"text": "world"}}))
    assert out["text"] == "WORLD"


async def test_llm_builtin_uses_gateway(invoker) -> None:
    out = await invoker.invoke(ToolInvocation(_tool("llm"), {"prompt": "summarize"}, {}))
    assert out["completion"].startswith("[fake:")
    assert "summarize" in out["completion"]


async def test_unknown_builtin_raises(invoker) -> None:
    with pytest.raises(BuiltinNotFoundError):
        await invoker.invoke(ToolInvocation(_tool("nope"), {}, {}))


async def test_non_builtin_kind_is_deferred(invoker) -> None:
    with pytest.raises(ToolKindNotSupportedError):
        await invoker.invoke(ToolInvocation(_tool("fetch", ToolKind.HTTP), {}, {}))
