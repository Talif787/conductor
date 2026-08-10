"""Tool invokers: dispatch by kind, with builtin handlers fully implemented."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.application.execution.ports import (
    LLMGateway,
    LLMRequest,
    ToolInvocation,
    ToolInvoker,
)
from app.domain.execution.errors import BuiltinNotFoundError, ToolKindNotSupportedError
from app.domain.tools.value_objects import ToolKind


class CompositeToolInvoker(ToolInvoker):
    """Route an invocation to the invoker registered for the tool's kind."""

    def __init__(self, builtin: ToolInvoker) -> None:
        self._builtin = builtin

    async def invoke(self, invocation: ToolInvocation) -> dict[str, Any]:
        if invocation.tool.kind is ToolKind.BUILTIN:
            return await self._builtin.invoke(invocation)
        raise ToolKindNotSupportedError(invocation.tool.kind.value)


BuiltinHandler = Callable[["BuiltinToolInvoker", ToolInvocation], Awaitable[dict[str, Any]]]


class BuiltinToolInvoker(ToolInvoker):
    """Runs builtin tools, resolved by tool name against a fixed registry."""

    def __init__(self, llm: LLMGateway) -> None:
        self._llm = llm

    async def invoke(self, invocation: ToolInvocation) -> dict[str, Any]:
        handler = _BUILTINS.get(invocation.tool.name)
        if handler is None:
            raise BuiltinNotFoundError(invocation.tool.name)
        return await handler(self, invocation)

    @property
    def llm(self) -> LLMGateway:
        return self._llm


async def _echo(_: BuiltinToolInvoker, invocation: ToolInvocation) -> dict[str, Any]:
    return {"parameters": invocation.parameters, "inputs": invocation.inputs}


async def _uppercase(_: BuiltinToolInvoker, invocation: ToolInvocation) -> dict[str, Any]:
    text = invocation.parameters.get("text", "")
    if not text:
        for upstream in invocation.inputs.values():
            if isinstance(upstream, dict) and upstream.get("text"):
                text = upstream["text"]
                break
    return {"text": str(text).upper()}


async def _llm(invoker: BuiltinToolInvoker, invocation: ToolInvocation) -> dict[str, Any]:
    prompt = invocation.parameters.get("prompt")
    if not prompt:
        parts = []
        for upstream in invocation.inputs.values():
            if isinstance(upstream, dict):
                parts.append(str(upstream.get("text") or upstream.get("completion") or upstream))
            else:
                parts.append(str(upstream))
        prompt = "\n".join(p for p in parts if p) or invocation.parameters.get("goal", "")
    model = str(invocation.parameters.get("model", "conductor-default"))
    response = await invoker.llm.complete(LLMRequest(prompt=str(prompt), model=model))
    return {"completion": response.text, "model": response.model}


_BUILTINS: dict[str, BuiltinHandler] = {
    "echo": _echo,
    "uppercase": _uppercase,
    "llm": _llm,
}
