from __future__ import annotations

import pytest

from app.application.execution.ports import ToolInvocation, ToolInvoker
from app.domain.execution.value_objects import ExecutionStatus
from app.domain.run.entities import Run
from app.domain.run.value_objects import Goal
from app.domain.shared.identifiers import TenantId
from app.domain.tools.entities import Tool
from app.domain.tools.value_objects import ToolKind
from app.domain.workflows.value_objects import Step, WorkflowDefinition
from app.infrastructure.execution.local_engine import LocalExecutionEngine


class RecordingInvoker(ToolInvoker):
    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on = fail_on

    async def invoke(self, invocation: ToolInvocation) -> dict:
        self.calls.append(invocation.tool.name)
        if self.fail_on and invocation.tool.name == self.fail_on:
            raise RuntimeError(f"boom in {invocation.tool.name}")
        return {"by": invocation.tool.name, "seen": sorted(invocation.inputs.keys())}


def _tool(name: str) -> Tool:
    return Tool.register(
        tenant_id=TenantId.new(),
        name=name,
        kind=ToolKind.BUILTIN,
        input_schema={},
        output_schema={},
    )


def _run() -> Run:
    return Run.create(tenant_id=TenantId.new(), goal=Goal("go"), parameters={})


def _defn(*steps: Step) -> WorkflowDefinition:
    return WorkflowDefinition(steps=tuple(steps))


async def test_linear_runs_in_order() -> None:
    a, b, c = _tool("a"), _tool("b"), _tool("c")
    tools = {str(a.id): a, str(b.id): b, str(c.id): c}
    definition = _defn(
        Step("a", "a", str(a.id)),
        Step("b", "b", str(b.id), ("a",)),
        Step("c", "c", str(c.id), ("b",)),
    )
    invoker = RecordingInvoker()
    execution = await LocalExecutionEngine(invoker).execute(_run(), definition, tools)
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert invoker.calls == ["a", "b", "c"]


async def test_diamond_threads_both_upstreams_into_join() -> None:
    t = {n: _tool(n) for n in "abcd"}
    tools = {str(v.id): v for v in t.values()}
    definition = _defn(
        Step("a", "a", str(t["a"].id)),
        Step("b", "b", str(t["b"].id), ("a",)),
        Step("c", "c", str(t["c"].id), ("a",)),
        Step("d", "d", str(t["d"].id), ("b", "c")),
    )
    invoker = RecordingInvoker()
    execution = await LocalExecutionEngine(invoker).execute(_run(), definition, tools)
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert invoker.calls[0] == "a" and invoker.calls[-1] == "d"
    join = next(s for s in execution.steps if s.step_id == "d")
    assert join.output["seen"] == ["b", "c"]


async def test_failure_skips_only_downstream() -> None:
    t = {n: _tool(n) for n in "abce"}
    tools = {str(v.id): v for v in t.values()}
    definition = _defn(
        Step("a", "a", str(t["a"].id)),
        Step("b", "b", str(t["b"].id), ("a",)),
        Step("c", "c", str(t["c"].id), ("b",)),
        Step("e", "e", str(t["e"].id)),
    )
    invoker = RecordingInvoker(fail_on="b")
    execution = await LocalExecutionEngine(invoker).execute(_run(), definition, tools)
    status = {s.step_id: s.status for s in execution.steps}
    assert status == {
        "a": ExecutionStatus.SUCCEEDED,
        "b": ExecutionStatus.FAILED,
        "c": ExecutionStatus.SKIPPED,
        "e": ExecutionStatus.SUCCEEDED,
    }
    assert execution.status is ExecutionStatus.FAILED
    assert "c" not in invoker.calls


async def test_unregistered_tool_fails_step() -> None:
    a = _tool("a")
    definition = _defn(Step("a", "a", "missing"))
    execution = await LocalExecutionEngine(RecordingInvoker()).execute(
        _run(), definition, {str(a.id): a}
    )
    assert execution.steps[0].status is ExecutionStatus.FAILED
    assert "not registered" in execution.steps[0].error


@pytest.mark.parametrize("concurrency", [1, 4])
async def test_all_steps_recorded_regardless_of_concurrency(concurrency: int) -> None:
    t = {n: _tool(n) for n in "abc"}
    tools = {str(v.id): v for v in t.values()}
    definition = _defn(
        Step("a", "a", str(t["a"].id)),
        Step("b", "b", str(t["b"].id)),
        Step("c", "c", str(t["c"].id), ("a", "b")),
    )
    execution = await LocalExecutionEngine(RecordingInvoker(), max_concurrency=concurrency).execute(
        _run(), definition, tools
    )
    assert {s.step_id for s in execution.steps} == {"a", "b", "c"}
    assert execution.status is ExecutionStatus.SUCCEEDED
