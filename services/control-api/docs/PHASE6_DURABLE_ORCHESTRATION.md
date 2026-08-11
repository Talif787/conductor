# Phase 6: Durable Orchestration with Temporal

Phase 6 adds a second execution engine that runs a published workflow's DAG as a
durable Temporal workflow. It is additive and opt-in: the default engine is still
the in-process local engine from Phase 4, so every existing test, the CI suite,
and the default runtime path are unchanged.

## Why Temporal

The local engine runs a DAG inside the API process. If the process restarts
mid-run, in-flight work is lost. Temporal persists workflow state and history, so
a run survives worker restarts, retries failed steps under a policy, and gives an
auditable execution timeline in the Temporal UI. That durability is the point of
this phase.

## Choosing an engine

Selection is driven by one setting (`CONDUCTOR_EXEC_ENGINE`):

- `local` (default): in-process `LocalExecutionEngine`. Nothing imports temporalio.
- `temporal`: `TemporalExecutionEngine`, which dispatches to a Temporal cluster.

The provider imports the Temporal engine lazily, only when `temporal` is selected,
so the default path never imports the SDK.

## Architecture

Three thin pieces sit behind the existing `ExecutionEngine` port, and the actual
tool execution reuses code that is already tested:

- Workflow (`ConductorRunWorkflow`): deterministic DAG orchestration. It computes
  ready and skipped steps wave by wave using the pure helpers in
  `application/execution/planning.py`, runs each ready step as an activity
  (concurrently within a wave), threads each step's output to its dependents, and
  marks downstream steps skipped after an upstream failure. Timestamps come from
  `workflow.now()` and ordering is list based (no set iteration), so the workflow
  is replay safe.
- Activity (`ExecutionActivities.run_tool`): the durable, side-effecting unit. It
  loads the tool from the repository and delegates to the same
  `CompositeToolInvoker` (builtin, HTTP, MCP) used by the local engine, so the
  tool-execution logic is identical and already verified.
- Engine (`TemporalExecutionEngine`): a thin adapter. It maps the run and
  definition to a serializable input (`temporal_mapping.to_workflow_input`),
  connects a client, starts the workflow, waits for the result, and maps it back
  to a `RunExecution` (`temporal_mapping.to_run_execution`).

The DTOs crossing the Temporal boundary (`temporal_dtos.py`) are plain dataclasses
so the SDK's default data converter serializes them over JSON.

## What is verified, and what is not

The framework-free logic is unit tested and runs in CI without a cluster:

- `planning.py`: wave ordering, ready and skip selection, cycle and unknown
  dependency rejection, and the run summary (parity with the local engine).
- `temporal_mapping.py`: both mapping directions.

The four modules that import temporalio (`activities.py`, `workflow.py`,
`engine.py`, `worker.py`) are syntax and import checked. CI installs temporalio,
so it imports these modules, but CI cannot run a Temporal cluster. Their runtime
behavior is validated on a machine with a running Temporal dev server and worker,
using the runbook below. Expect the possibility of a fix round against real
cluster errors: this is the first engine whose end to end path cannot be fully
reproduced in the sandbox.

## Retry semantics

`CONDUCTOR_TEMPORAL_ACTIVITY_MAX_ATTEMPTS` defaults to `1`, which matches the
local engine: a failing step fails once, downstream steps are skipped, and the run
fails with the same summary message. Raising it turns on Temporal's durable
retries, which is the main reason to move a workload onto Temporal. It is left at
`1` by default so behavior is identical to the local engine until you opt into
retries.

## Settings (`CONDUCTOR_TEMPORAL_*`)

| Setting | Env var | Default |
| --- | --- | --- |
| Server address | `CONDUCTOR_TEMPORAL_HOST` | `localhost:7233` |
| Namespace | `CONDUCTOR_TEMPORAL_NAMESPACE` | `default` |
| Task queue | `CONDUCTOR_TEMPORAL_TASK_QUEUE` | `conductor-runs` |
| Workflow timeout (s) | `CONDUCTOR_TEMPORAL_WORKFLOW_EXECUTION_TIMEOUT_SECONDS` | `300` |
| Activity timeout (s) | `CONDUCTOR_TEMPORAL_ACTIVITY_START_TO_CLOSE_TIMEOUT_SECONDS` | `60` |
| Activity attempts | `CONDUCTOR_TEMPORAL_ACTIVITY_MAX_ATTEMPTS` | `1` |

Engine selection uses `CONDUCTOR_EXEC_ENGINE` (`local` or `temporal`).

## Runbook (local, Cloud Shell)

You need four things running: Postgres, a Temporal dev server, a Conductor worker,
and the API with the Temporal engine selected.

1. Postgres and migrations (as in earlier phases):

   ```
   cd ~/conductor/services/control-api
   docker compose up -d --wait postgres
   alembic upgrade head
   ```

2. Install the Temporal CLI and start a dev server. The dev server exposes the
   gRPC endpoint on `7233` and the Web UI on `8233`, and creates the `default`
   namespace:

   ```
   curl -sSf https://temporal.download/cli.sh | sh
   export PATH="$HOME/.temporalio/bin:$PATH"
   temporal server start-dev
   ```

3. In a second shell, start the Conductor worker (hosts the workflow and the tool
   activity):

   ```
   cd ~/conductor/services/control-api
   source ~/conductor/.venv/bin/activate
   make worker
   ```

4. In a third shell, run the API with the Temporal engine selected:

   ```
   cd ~/conductor/services/control-api
   source ~/conductor/.venv/bin/activate
   CONDUCTOR_EXEC_ENGINE=temporal make run
   ```

5. Smoke test. Use the same curl flow as Phase 4 and Phase 5 (register a tenant to
   get a token, register a builtin tool, author and publish a one or two step
   workflow, create a run), then execute the run:

   ```
   curl -sS -X POST localhost:8000/api/v1/runs/$RUN_ID/execute \
     -H "authorization: Bearer $TOKEN" | jq .
   ```

   The request dispatches to Temporal instead of running in process. Watch the
   worker log for activity execution, open the Temporal UI at
   `http://localhost:8233` to see the workflow `conductor-run-$RUN_ID`, and fetch
   the stored result:

   ```
   curl -sS localhost:8000/api/v1/runs/$RUN_ID/execution \
     -H "authorization: Bearer $TOKEN" | jq '.status, .steps[].status'
   ```

   A healthy run reports `succeeded` with each step `succeeded`, matching what the
   local engine produces for the same workflow.

## Future work

- A containerized Temporal cluster (auto-setup plus UI) behind a compose profile,
  once its service wiring is validated on a real machine. Local dev uses the CLI
  dev server for now.
- Turning on durable retries and per-activity heartbeat and timeout tuning.
- Surfacing the Temporal workflow id on the run record for direct UI linking.
