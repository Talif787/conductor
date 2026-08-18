# Conductor

Control plane and data plane for an Agentic AI Workflow Automation Platform.
Users define goals, a governed agent plans and executes multi-step workflows
through MCP tools, with durable execution, human-in-the-loop approvals, and
reasoning-level observability.

The platform is built and deployed to production on a $0/month stack (Vercel,
Render, Neon). See "Production deployment" below.

## Live deployment

| Surface | URL |
|---|---|
| Frontend (conductor-web) | https://conductor-web-theta.vercel.app |
| Backend API (control-api) | https://conductor-api-8ioh.onrender.com |
| API health | https://conductor-api-8ioh.onrender.com/readyz |

The backend runs on a free tier that sleeps after 15 minutes idle, so the first
request after a quiet period takes 30 to 60 seconds to wake. This is expected.

## Services

| Path | Description | Status |
|---|---|---|
| services/control-api | FastAPI control plane (runs, workflows, tools, execution, approvals, governance) | Live in production |
| services/agent-worker | Temporal-based agent runtime (deterministic loop) | Planned (Temporal deferred; execution currently runs in-process) |
| services/tool-gateway | Sandboxed MCP tool execution | Planned |
| conductor-web | Next.js 15 frontend (separate repository) | Live in production |

## Phase roadmap

Status reflects the deployed platform. Where a phase was delivered in a reduced
form to fit the $0 deployment, that is noted honestly.

1. Control-plane foundation and Run Execution context. Done.
2. Identity and Tenancy (OIDC/JWT, RBAC). Done.
3. Workflow Authoring and Tool Registry. Done.
4. Agent Runtime (Temporal, LLM gateway, MCP tool gateway). LLM gateway and
   run/step execution done; Temporal and a standalone tool gateway are deferred,
   execution runs in-process for now.
5. Governance (approval gates, policy). Approval gates done.
6. Observability and eventing (OTel, eventing, CQRS projections, cost). OTel
   tracing, the run-view read model, and per-run/per-step cost tracking done;
   Kafka is deferred in favor of an in-process outbox relay.
7. Next.js frontend. Done and deployed.
8. DevOps and deployment. Done as a $0 stack: Render Blueprint for the backend,
   Vercel for the frontend, Neon for the database, Terraform for GitHub
   governance and DNS, CI/CD with security scanning, free daily backups, and a
   full operator documentation set. See docs/deployment/.
9. Hardening (rate limiting, WAF, scanning, load and chaos tests). Supply-chain
   and code scanning done (Trivy, gitleaks, Bandit, Dependabot); rate limiting
   and WAF are pending (see the security audit in docs/deployment/).

## Quick start (control-api)

```
cd services/control-api
cp .env.example .env
docker compose up --build     # postgres, migrations, api on :8000
```

Open the API docs at http://localhost:8000/docs and metrics at /metrics.

See services/control-api/README.md for local development without Docker.

## Production deployment

The platform is deployed to a completely free ($0/month) stack. The full
guide and operator documentation live in docs/deployment/:

- DEPLOYMENT.md: end-to-end deployment guide (accounts, env, staging, production).
- ARCHITECTURE.md: the deployed architecture and design decisions.
- ENVIRONMENT_VARIABLES.md: every environment variable across backend and frontend.
- RUNBOOK.md: routine operational procedures.
- INCIDENT_RESPONSE.md: diagnosis and remediation for failures.
- DISASTER_RECOVERY.md: backup, restore, and full-rebuild runbooks.

The deployment decision docs (platform selection, backend, frontend, database,
CI/CD, IaC, observability) are the numbered files 01 through 07 in the same
folder.

Hosting summary: frontend on Vercel Hobby, backend on a Render free web service,
database on Neon free (PostgreSQL 18). No Redis, Kafka, object storage, or
WebSockets. Backups run daily via a GitHub Actions pg_dump to an artifact.
Error tracking via Sentry (free tier); uptime via UptimeRobot or Better Stack.

## Documentation

- CONTRIBUTING.md: branch strategy, commit conventions, and the quality gate.
- docs/DEVELOPMENT_SETUP.md: Cloud Shell, GitHub, and Google Cloud (WIF) setup.
- docs/ARCHITECTURE.md: code-level architecture.
- docs/deployment/: production deployment and operator documentation.
- services/control-api/docs/PHASE1_RUNBOOK.md: set up, run, and test the control-api.
