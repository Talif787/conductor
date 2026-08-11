# Phase 7: Governance (Policy Enforcement and Human Approvals)

Phase 7 adds a governance gate in front of run execution. Every execution
request is evaluated by a policy decision point that returns one of three
effects: allow, deny, or require approval. A deny stops the run, an allow runs
it immediately as before, and a require approval parks the run behind a human
approval request until an authorized user approves or rejects it.

The design mirrors the Phase 6 durable orchestration pattern: a tested
in-process default (the local evaluator) plus an opt-in external adapter (Open
Policy Agent) behind a single port, selected by configuration. With no rules
configured the local evaluator allows everything, so behavior is unchanged until
governance is switched on.

## Architecture

The `PolicyDecisionPoint` port (`app/application/governance/policy.py`) takes a
serializable `PolicyQuery` (tenant, principal, roles, run, referenced tools) and
returns a `PolicyDecision` (effect plus reason). Two adapters implement it:

- `LocalPolicyEvaluator` (`app/infrastructure/governance/local_policy.py`): the
  default. Deterministic, dependency free, driven by configuration.
- `OpaPolicyDecisionPoint` (`app/infrastructure/governance/opa_policy.py`):
  opt-in. Posts the query to OPA and maps the returned document to a decision.

Governance runs in a new `SubmitRunHandler`, the governed entry point that the
execute endpoint calls. The existing `ExecuteRunHandler` is unchanged in
contract and remains the low-level executor that drives the DAG. On allow the
submit handler delegates to the executor; on require approval it opens an
`ApprovalRequest` and moves the run to `awaiting_approval`; on deny it fails the
run and raises. Approving a request drives the parked run through the same
executor; rejecting fails it.

### Run lifecycle additions

`RunStatus.AWAITING_APPROVAL` is a new non-terminal state. Allowed transitions:

```
queued -> awaiting_approval        (policy requires approval)
awaiting_approval -> planning      (approved, execution proceeds)
awaiting_approval -> failed        (rejected)
awaiting_approval -> cancelled
```

The runs table stores status as text, so no run migration is required.

## API changes

`POST /api/v1/runs/{id}/execute` is now governed and returns one of:

- `200 OK` with the execution result (allow, unchanged contract).
- `202 Accepted` with the approval request body (require approval).
- `403 Forbidden` problem+json (deny).

New approval endpoints:

- `GET /api/v1/approvals` (permission `runs:read`, optional `status` filter).
- `GET /api/v1/approvals/{id}` (permission `runs:read`).
- `POST /api/v1/approvals/{id}/approve` (permission `runs:approve`), returns the
  resulting execution.
- `POST /api/v1/approvals/{id}/reject` (permission `runs:approve`), returns the
  decided approval.

### RBAC

A new `runs:approve` permission is granted to the AUTHOR, ADMIN, and OWNER
roles. OPERATOR and VIEWER cannot approve.

## Configuration

All governance settings use the `CONDUCTOR_POLICY_` prefix.

| Variable | Default | Meaning |
| --- | --- | --- |
| `CONDUCTOR_POLICY_ENGINE` | `local` | `local` or `opa` |
| `CONDUCTOR_POLICY_REQUIRE_APPROVAL_FOR_HIGH_PRIORITY` | `false` | high priority runs need approval |
| `CONDUCTOR_POLICY_REQUIRE_APPROVAL_FOR_EXTERNAL_TOOLS` | `false` | runs using http or mcp tools need approval |
| `CONDUCTOR_POLICY_DENIED_TOOL_KINDS` | `[]` | tool kinds that are denied outright |
| `CONDUCTOR_POLICY_OPA_URL` | `http://localhost:8181` | OPA base URL |
| `CONDUCTOR_POLICY_OPA_DECISION_PATH` | `v1/data/conductor/decision` | OPA decision path |
| `CONDUCTOR_POLICY_OPA_FAIL_CLOSED` | `true` | deny when OPA is unreachable |

The deny rule always takes precedence over require approval.

## Local demo (no external services)

Enable the high priority rule and restart the API:

```bash
export CONDUCTOR_POLICY_REQUIRE_APPROVAL_FOR_HIGH_PRIORITY=true
make run
```

Create a high priority run, then execute it. The execute call returns 202 with a
pending approval instead of running:

```bash
# create a high priority run against a published workflow, capture RUN_ID
curl -sS -X POST localhost:8000/api/v1/runs/$RUN_ID/execute \
  -H "Authorization: Bearer $TOKEN" -i | head -n 1
# HTTP/1.1 202 Accepted

# list pending approvals, capture APPROVAL_ID
curl -sS localhost:8000/api/v1/approvals?status=pending \
  -H "Authorization: Bearer $TOKEN"

# approve it: the parked run now executes and the execution is returned
curl -sS -X POST localhost:8000/api/v1/approvals/$APPROVAL_ID/approve \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"note": "reviewed and approved"}'
```

Rejecting instead fails the run:

```bash
curl -sS -X POST localhost:8000/api/v1/approvals/$APPROVAL_ID/reject \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"note": "not this quarter"}'
```

## OPA runbook (opt-in)

The OPA adapter posts `{"input": <policy query>}` to the decision path and reads
the `result` field, expecting a document shaped like
`{"effect": "allow|deny|require_approval", "reason": "..."}`. A boolean result is
also accepted (true means allow, false means deny).

Sample policy (`conductor.rego`):

```rego
package conductor

import future.keywords.if
import future.keywords.in

# deny wins, then require_approval, otherwise allow
decision := {"effect": "deny", "reason": "mcp tools are not permitted"} if {
    some tool in input.tools
    tool.kind == "mcp"
} else := {"effect": "require_approval", "reason": "high priority runs require approval"} if {
    input.priority == "high"
} else := {"effect": "allow", "reason": ""}
```

Run OPA as a server and point Conductor at it:

```bash
opa run --server --addr :8181 conductor.rego

export CONDUCTOR_POLICY_ENGINE=opa
export CONDUCTOR_POLICY_OPA_URL=http://localhost:8181
export CONDUCTOR_POLICY_OPA_DECISION_PATH=v1/data/conductor/decision
make run
```

Execution now consults OPA on every submit. If OPA is unreachable the adapter
fails closed (deny) by default; set `CONDUCTOR_POLICY_OPA_FAIL_CLOSED=false` to
fail open during development.

## Verification boundary

The local evaluator, the approval state machine, and the full submit, approve,
reject, and deny flows are covered by framework free unit tests
(`tests/unit/test_local_policy.py`, `test_approval_request.py`,
`test_submit_run_handler.py`) that run in CI without a database or any external
service. The OPA adapter is import checked and type checked in CI; its live
behavior against a running OPA server is validated by the runbook above, not by
CI, exactly as the Temporal engine runtime is validated by its smoke test.
