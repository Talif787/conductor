# Conductor

Control plane and data plane for an Agentic AI Workflow Automation Platform.
Users define goals, a governed agent plans and executes multi-step workflows
through MCP tools, with durable execution, human-in-the-loop approvals, and
reasoning-level observability.

This repository is delivered in phases. See the phase roadmap below. Each phase
is independently buildable and testable.

## Services

| Path | Description | Status |
|---|---|---|
| services/control-api | FastAPI control plane (runs, workflows, tools, governance) | Phase 1: Run Execution context |
| services/agent-worker | Temporal-based agent runtime (deterministic loop) | Planned (Phase 4) |
| services/tool-gateway | Sandboxed MCP tool execution | Planned (Phase 4) |

## Phase roadmap

1. Control-plane foundation and Run Execution context (this phase)
2. Identity and Tenancy (OIDC/JWT, RBAC/ABAC)
3. Workflow Authoring and Tool Registry
4. Agent Runtime (Temporal, LLM gateway, MCP tool gateway)
5. Governance (OPA policy, approval gates)
6. Observability depth and eventing (OTel nesting, Kafka, CQRS projections, cost)
7. Next.js frontend
8. Full DevOps (Helm, Terraform, canary, DR)
9. Hardening (rate limiting, WAF, scanning, load and chaos tests)

## Quick start (control-api)

```
cd services/control-api
cp .env.example .env
docker compose up --build     # postgres, migrations, api on :8000
```

Open the API docs at http://localhost:8000/docs and metrics at /metrics.

See services/control-api/README.md for local development without Docker.

## Documentation

- CONTRIBUTING.md: branch strategy, commit conventions, and the quality gate.
- docs/DEVELOPMENT_SETUP.md: Cloud Shell, GitHub, and Google Cloud (WIF) setup.
- docs/ARCHITECTURE.md: code-level architecture for Phase 1.
- services/control-api/docs/PHASE1_RUNBOOK.md: set up, run, and test Phase 1.
