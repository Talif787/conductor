"""Unit tests for LLM cost tracking through the execution path."""

from __future__ import annotations

from app.application.execution.ports import LLMRequest, ToolInvocation
from app.domain.execution.pricing import TokenPricing, estimate_cost_usd
from app.domain.execution.value_objects import ExecutionStatus
from app.domain.run.entities import Run
from app.domain.run.value_objects import Goal
from app.domain.shared.identifiers import TenantId
from app.domain.tools.entities import Tool
from app.domain.tools.value_objects import ToolKind
from app.domain.workflows.value_objects import Step, WorkflowDefinition
from app.infrastructure.execution.local_engine import LocalExecutionEngine
from app.infrastructure.execution.tool_invoker import BuiltinToolInvoker
from app.infrastructure.llm.gateway import FakeLLMGateway


def _tool(name: str) -> Tool:
    return Tool.register(
        tenant_id=TenantId.new(),
        name=name,
        kind=ToolKind.BUILTIN,
        input_schema={},
        output_schema={},
    )


def _run(parameters: dict) -> Run:
    return Run.create(tenant_id=TenantId.new(), goal=Goal("go"), parameters=parameters)


def test_estimate_cost_usd_applies_pricing() -> None:
    pricing = TokenPricing(prompt_usd_per_1k=0.001, completion_usd_per_1k=0.002)
    cost = estimate_cost_usd({"prompt_tokens": 1000, "completion_tokens": 500}, pricing)
    assert cost == round(0.001 + 0.001, 6)


def test_estimate_cost_usd_defaults_to_zero_without_usage() -> None:
    assert estimate_cost_usd({}, TokenPricing()) == 0.0


async def test_fake_gateway_reports_token_usage() -> None:
    response = await FakeLLMGateway().complete(LLMRequest(prompt="a b c", model="m"))
    assert response.usage["prompt_tokens"] == 3
    assert response.usage["completion_tokens"] == len(response.text.split())
    assert response.usage["total_tokens"] == (
        response.usage["prompt_tokens"] + response.usage["completion_tokens"]
    )


async def test_llm_builtin_output_keeps_completion_and_adds_usage() -> None:
    invoker = BuiltinToolInvoker(FakeLLMGateway())
    out = await invoker.invoke(ToolInvocation(_tool("llm"), {"prompt": "summarize"}, {}))
    assert out["completion"].startswith("[fake:")
    assert out["usage"]["prompt_tokens"] == 1


async def test_engine_aggregates_run_cost_from_llm_step() -> None:
    llm = _tool("llm")
    definition = WorkflowDefinition(steps=(Step("s1", "s1", str(llm.id)),))
    engine = LocalExecutionEngine(BuiltinToolInvoker(FakeLLMGateway()))
    execution = await engine.execute(
        _run({"prompt": "summarize the quarterly report"}),
        definition,
        {str(llm.id): llm},
    )
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.steps[0].cost_usd > 0
    assert execution.total_cost_usd == round(execution.steps[0].cost_usd, 6)


async def test_non_llm_step_incurs_no_cost() -> None:
    echo = _tool("echo")
    definition = WorkflowDefinition(steps=(Step("e", "e", str(echo.id)),))
    engine = LocalExecutionEngine(BuiltinToolInvoker(FakeLLMGateway()))
    execution = await engine.execute(_run({}), definition, {str(echo.id): echo})
    assert execution.steps[0].cost_usd == 0.0
    assert execution.total_cost_usd == 0.0
