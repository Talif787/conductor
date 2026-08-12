"""In-process concurrent DAG execution engine.

Runs a published workflow's steps in dependency order, executing independent
steps concurrently, threading each step's output to its dependents, and marking
downstream steps skipped when an upstream step fails.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.application.execution.ports import ExecutionEngine, ToolInvocation, ToolInvoker
from app.domain.execution.entities import RunExecution, StepExecution
from app.domain.execution.pricing import TokenPricing, estimate_cost_usd
from app.domain.execution.value_objects import ExecutionStatus
from app.domain.run.entities import Run
from app.domain.shared.identifiers import RunExecutionId, StepExecutionId
from app.domain.tools.entities import Tool
from app.domain.workflows.value_objects import Step, WorkflowDefinition
from app.infrastructure.observability.metrics import LLM_COST_USD_TOTAL

_FAILED_OR_SKIPPED = {ExecutionStatus.FAILED, ExecutionStatus.SKIPPED}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LocalExecutionEngine(ExecutionEngine):
    def __init__(
        self,
        invoker: ToolInvoker,
        max_concurrency: int = 8,
        pricing: TokenPricing | None = None,
    ) -> None:
        self._invoker = invoker
        self._max_concurrency = max(1, max_concurrency)
        self._pricing = pricing or TokenPricing()

    async def execute(
        self,
        run: Run,
        definition: WorkflowDefinition,
        tools: dict[str, Tool],
    ) -> RunExecution:
        started_at = _utcnow()
        steps = list(definition.steps)
        by_id = {step.step_id: step for step in steps}
        deps = {step.step_id: set(step.depends_on) for step in steps}
        position = {step.step_id: index for index, step in enumerate(steps)}
        status: dict[str, ExecutionStatus] = dict.fromkeys(by_id, ExecutionStatus.PENDING)
        outputs: dict[str, dict] = {}
        records: dict[str, StepExecution] = {}
        remaining = set(by_id)
        semaphore = asyncio.Semaphore(self._max_concurrency)

        while remaining:
            for sid in [s for s in remaining if deps[s] & _skipped_or_failed(status, deps[s])]:
                status[sid] = ExecutionStatus.SKIPPED
                records[sid] = _skipped_record(by_id[sid], position[sid])
                remaining.discard(sid)
            if not remaining:
                break

            ready = [
                sid
                for sid in remaining
                if all(status[dep] is ExecutionStatus.SUCCEEDED for dep in deps[sid])
            ]
            if not ready:
                break

            results = await asyncio.gather(
                *(
                    self._run_step(by_id[sid], tools, run, outputs, position[sid], semaphore)
                    for sid in ready
                )
            )
            for sid, record in zip(ready, results, strict=True):
                records[sid] = record
                status[sid] = record.status
                if record.status is ExecutionStatus.SUCCEEDED and record.output is not None:
                    outputs[sid] = record.output
                remaining.discard(sid)

        ordered = [records[step.step_id] for step in steps if step.step_id in records]
        overall, error = _summarize(ordered)
        total_cost = round(sum(s.cost_usd for s in ordered), 6)
        return RunExecution(
            id=RunExecutionId.new(),
            run_id=run.id,
            tenant_id=run.tenant_id,
            status=overall,
            started_at=started_at,
            finished_at=_utcnow(),
            error=error,
            steps=ordered,
            total_cost_usd=total_cost,
        )

    async def _run_step(
        self,
        step: Step,
        tools: dict[str, Tool],
        run: Run,
        outputs: dict[str, dict],
        position: int,
        semaphore: asyncio.Semaphore,
    ) -> StepExecution:
        started_at = _utcnow()
        record = StepExecution(
            id=StepExecutionId.new(),
            step_id=step.step_id,
            tool_id=step.tool_id,
            position=position,
            status=ExecutionStatus.RUNNING,
            started_at=started_at,
        )
        tool = tools.get(step.tool_id)
        if tool is None:
            record.status = ExecutionStatus.FAILED
            record.error = f"tool '{step.tool_id}' is not registered"
            record.finished_at = _utcnow()
            return record

        invocation = ToolInvocation(
            tool=tool,
            parameters=run.parameters,
            inputs={dep: outputs.get(dep, {}) for dep in step.depends_on},
        )
        try:
            async with semaphore:
                output = await self._invoker.invoke(invocation)
            record.status = ExecutionStatus.SUCCEEDED
            record.output = output
            record.cost_usd = self._step_cost(output)
        except Exception as exc:  # noqa: BLE001
            record.status = ExecutionStatus.FAILED
            record.error = str(exc)
        record.finished_at = _utcnow()
        return record

    def _step_cost(self, output: dict) -> float:
        usage = output.get("usage") if isinstance(output, dict) else None
        if not isinstance(usage, dict):
            return 0.0
        cost = estimate_cost_usd(usage, self._pricing)
        if cost > 0:
            model = str(output.get("model", "unknown"))
            LLM_COST_USD_TOTAL.labels(model=model).inc(cost)
        return cost


def _skipped_or_failed(status: dict[str, ExecutionStatus], dependencies: set[str]) -> set[str]:
    return {dep for dep in dependencies if status[dep] in _FAILED_OR_SKIPPED}


def _skipped_record(step: Step, position: int) -> StepExecution:
    now = _utcnow()
    return StepExecution(
        id=StepExecutionId.new(),
        step_id=step.step_id,
        tool_id=step.tool_id,
        position=position,
        status=ExecutionStatus.SKIPPED,
        error="skipped after an upstream failure",
        started_at=now,
        finished_at=now,
    )


def _summarize(records: list[StepExecution]) -> tuple[ExecutionStatus, str | None]:
    failed = [r for r in records if r.status is ExecutionStatus.FAILED]
    skipped = [r for r in records if r.status is ExecutionStatus.SKIPPED]
    if failed:
        first = failed[0]
        return ExecutionStatus.FAILED, f"step '{first.step_id}' failed: {first.error}"
    if skipped:
        return ExecutionStatus.FAILED, "one or more steps were skipped after an upstream failure"
    return ExecutionStatus.SUCCEEDED, None
