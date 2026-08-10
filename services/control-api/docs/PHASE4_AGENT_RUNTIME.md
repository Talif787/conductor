# Phase 4: Agent Runtime (Execution Engine and LLM Gateway)

Phase 3 gave a tenant the ability to author a workflow (a DAG of steps, each bound
to a registered tool) and publish an immutable version. Phase 4 makes a published
workflow actually run. A queued run that references a published workflow version can
now be executed: its steps run in dependency order, independent steps run
concurrently, each step's output is threaded to its dependents, and the run finishes
in a terminal state with a per-step execution record.

This phase deliberately ships an in-process execution engine behind a port, not a
durable orchestrator. See the ADR at the end for why Temporal is Phase 5.

## What executes, and when

A run is created (Phase 1) in the `queued` state. Execution is an explicit action:

```
POST /api/v1/runs/{run_id}/execute
```

The `ExecuteRunHandler` drives the run through the state machine in three stages:

1. Load and validate, then move the run to `running`. The run must be `queued`, it
   must reference a workflow, and that workflow version must exist and be published
   in the caller's tenant. The run transitions `queued -> planning -> running` and
   that transition is committed before any tool work begins, so the run's status
   reflects that execution is under way.
2. Run the DAG outside any open transaction. Holding a database transaction open
   across tool calls (which may reach out to an LLM) would be an anti-pattern, so the
   engine runs between commits.
3. Persist the execution record and finalize the run as `completed` or `failed`.

If the engine itself raises unexpectedly, the run is marked `failed` with the error
attached, so a run never gets stranded in `running`.

Runs that carry only a goal and no workflow cannot be executed yet: that is the
agent-plans-its-own-steps path, which arrives in a later phase. Such a request is
rejected with `409 Conflict` (`run-not-executable`).

## The execution engine

`LocalExecutionEngine` (an adapter behind the `ExecutionEngine` port) is a wave-based
concurrent DAG scheduler. On each wave it:

1. Marks any remaining step whose dependency has failed or been skipped as `skipped`.
2. Selects the ready set: every step whose dependencies have all succeeded.
3. Runs the ready set concurrently with `asyncio.gather`, bounded by a semaphore
   sized from `CONDUCTOR_EXEC_MAX_CONCURRENCY`.
4. Threads each succeeded step's output into the input of its dependents.

Failure semantics are precise: a failing step fails only its own subtree. Independent
branches still run to completion, and the overall run is `failed` if any step failed
or was skipped, otherwise `succeeded`. Because published definitions are validated as
acyclic at publish time (Phase 3), the scheduler always makes progress.

Each step produces a `StepExecution` record with its status, output, error, position,
and start and finish timestamps. These are persisted in `run_step_executions` under a
parent `run_executions` row.

## Tools and the invocation port

The engine calls tools through the `ToolInvoker` port. `CompositeToolInvoker`
dispatches by the tool's kind:

- `builtin` is fully implemented by `BuiltinToolInvoker`.
- `http` and `mcp` are not executable by the local engine yet and raise a typed error
  (`tool-kind-unsupported`). They arrive with the external invocation adapter in
  Phase 5. A step bound to such a tool fails cleanly rather than crashing the run.

Builtin tools resolve by tool name against a small registry:

| Tool name   | Behavior                                                              |
|-------------|-----------------------------------------------------------------------|
| `echo`      | Returns the run parameters and the upstream inputs unchanged.         |
| `uppercase` | Uppercases `parameters.text`, or the first upstream `text` field.     |
| `llm`       | Builds a prompt from parameters or upstream text and calls the LLM.   |

To use a builtin, register a tool of kind `builtin` whose name matches a registry
entry, then reference it from a workflow step.

## The LLM gateway

LLM access sits behind the `LLMGateway` port so the provider stays swappable and
tests stay deterministic, the same pattern used for password hashers and token
services in Phase 2.

- `FakeLLMGateway` (default) returns a deterministic string of the form
  `[fake:{model}] {prompt}`. This is what runs in local development and in tests.
- `HttpLLMGateway` calls an OpenAI-compatible `/chat/completions` endpoint. It is
  selected by configuration and exercised only with real credentials.

Selection is by environment:

```
CONDUCTOR_LLM_PROVIDER=fake        # or "http"
CONDUCTOR_LLM_BASE_URL=https://api.openai.com/v1
CONDUCTOR_LLM_API_KEY=sk-...
CONDUCTOR_LLM_MODEL=conductor-default
CONDUCTOR_LLM_TIMEOUT_SECONDS=30
CONDUCTOR_EXEC_MAX_CONCURRENCY=8
```

## Endpoints

| Method | Path                              | Permission     | Purpose                          |
|--------|-----------------------------------|----------------|----------------------------------|
| POST   | `/api/v1/runs/{run_id}/execute`   | `runs:execute` | Execute a queued run's workflow. |
| GET    | `/api/v1/runs/{run_id}/execution` | `runs:read`    | Read the execution and steps.    |

`runs:execute` is a new permission granted to the operator role and above (operator,
author, admin, owner). Viewers cannot execute.

Both responses share this shape:

```json
{
  "run_id": "…",
  "status": "succeeded",
  "error": null,
  "started_at": "…",
  "finished_at": "…",
  "steps": [
    {
      "step_id": "fetch",
      "tool_id": "…",
      "position": 0,
      "status": "succeeded",
      "output": {"parameters": {}, "inputs": {}},
      "error": null,
      "started_at": "…",
      "finished_at": "…"
    }
  ]
}
```

## End-to-end smoke test

Assumes the API is running on port 8000 and `$TOKEN` holds an owner access token
(register or log in per the Phase 2 docs). The `authorization` value is the full
`Bearer <token>` string.

```bash
BASE=http://localhost:8000/api/v1
AUTH="Authorization: Bearer $TOKEN"

# 1. Register two builtin tools.
ECHO=$(curl -s -X POST "$BASE/tools" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"name":"echo","kind":"builtin","input_schema":{},"output_schema":{}}' | jq -r .id)
LLM=$(curl -s -X POST "$BASE/tools" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"name":"llm","kind":"builtin","input_schema":{},"output_schema":{}}' | jq -r .id)

# 2. Create a workflow, define a two-step DAG, and publish version 1.
WF=$(curl -s -X POST "$BASE/workflows" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"name":"Pipeline"}' | jq -r .id)

curl -s -X PUT "$BASE/workflows/$WF/versions/1" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"definition\":{\"steps\":[
        {\"step_id\":\"fetch\",\"tool_id\":\"$ECHO\"},
        {\"step_id\":\"sum\",\"tool_id\":\"$LLM\",\"depends_on\":[\"fetch\"]}]}}" > /dev/null

curl -s -X POST "$BASE/workflows/$WF/versions/1/publish" -H "$AUTH" > /dev/null

# 3. Create a run bound to the published version, then execute it.
RUN=$(curl -s -X POST "$BASE/runs" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"goal\":\"summarize the report\",\"parameters\":{\"prompt\":\"quarterly numbers\"},
       \"workflow_id\":\"$WF\",\"workflow_version\":\"1\"}" | jq -r .id)

curl -s -X POST "$BASE/runs/$RUN/execute" -H "$AUTH" | jq
curl -s "$BASE/runs/$RUN/execution" -H "$AUTH" | jq '.status, (.steps | length)'
```

The execute call returns `status: "succeeded"` with two succeeded steps; the `sum`
step's output carries the fake completion text.

## Data model

Migration `0004` adds two tables:

- `run_executions`: one row per execution attempt, foreign-keyed to `runs` with
  cascade delete, carrying tenant, status, error, and timing.
- `run_step_executions`: one row per step, foreign-keyed to `run_executions` with
  cascade delete, carrying step and tool ids, position, status, JSONB output, error,
  and timing.

## ADR: durable orchestration is deferred to Phase 5

The roadmap named Temporal alongside the engine and the LLM gateway. It is split out
deliberately.

Context. Every phase of this project is gated the same way: the crown-jewel logic is
verified in a sandbox behind ports and fakes, everything compiles, and the full test
and lint and type suite passes locally before merge. Temporal cannot be verified that
way without a running cluster, and its Python SDK imposes strict worker and
determinism rules (sandboxed workflow code, non-deterministic calls confined to
activities) that are easy to get subtly wrong when the code is never exercised. Live
HTTP and MCP tool calls have the same gap: there are no endpoints to test against.

Decision. Phase 4 ships an in-process `LocalExecutionEngine` behind the
`ExecutionEngine` port, with `ToolInvoker` and `LLMGateway` ports alongside it. The
engine, the builtin invoker, and the fake gateway are fully tested and run a real
concurrent DAG with real failure semantics.

Consequences. Durable orchestration becomes an adapter swap, not a rewrite. Phase 5
adds a Temporal cluster to compose, a worker process, and a `TemporalExecutionEngine`
that implements the same port, selected by `CONDUCTOR_EXEC_ENGINE`. The HTTP and MCP
tool invokers land in that phase as additional `ToolInvoker` dispatch targets. Until
then, `http` and `mcp` tools are registrable and can appear in workflows, but a step
bound to one fails cleanly with a clear message rather than pretending to run.
