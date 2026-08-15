# Conductor: $0/Month Production Deployment, Architecture and Platform Selection

This is the foundational decision document for deploying Conductor to production at a hard cost of $0/month. It covers the deployment dependency map, the platform selection with justifications and rejected alternatives, the target architecture, the three-environment strategy, and an honest cost and compromise ledger. Later documents in this set cover the concrete artifacts (Dockerfile, CI/CD workflows, IaC, observability) and the operational runbooks.

Free-tier terms were verified against current sources in August 2026. Free tiers change often; every figure here should be reconfirmed on the provider's pricing page before you rely on it. Where a capability cannot be provided for free, the limitation is stated explicitly and the closest $0 alternative is given, rather than introducing any paid service.

## 1. Deployment dependency map

Conductor is two repositories: `conductor-web` (Next.js 15 frontend) and `conductor` (the FastAPI control-api backend). The backend is the only stateful tier; it owns all data through PostgreSQL.

| Component | Runtime | Depends on | Infra needed | Chosen $0 host |
| --- | --- | --- | --- | --- |
| Frontend (conductor-web) | Next.js 15 / Node | backend API | edge + Node, static assets | Vercel Hobby |
| Backend (control-api) | Python 3.12 / FastAPI (Uvicorn) | PostgreSQL | always-on-ish container | Render free web service |
| Relay (read-model projector) | Python (`make relay`) | PostgreSQL | scheduled or background run | Render free cron job |
| Database | PostgreSQL 16 | none | managed Postgres | Neon free |
| Auth (JWT/RBAC) | in-process in the backend | PostgreSQL | none extra | (backend) |
| AI/LLM gateway | provider HTTP API | provider API key | secret storage only | provider free/pay-per-use key, key held server-side |

What Conductor does **not** need, which removes the components that are hardest to obtain for free:

- **No Redis / cache tier.** There is no cache layer in the codebase.
- **No Kafka.** The event path uses a transactional outbox drained by the relay into a Postgres read model; the message bus defaults to a null bus. Kafka and Temporal were deliberately deferred.
- **No object storage.** There are no file uploads.
- **No WebSockets.** No realtime transport.

Consequently, prompt sections covering Redis (9), message queues and workers as a separate Kafka tier (10), and object storage (11) are largely not applicable to this project. This is the single biggest reason a true $0 deployment is realistic here.

### Communication paths

- Browser to Frontend: HTTPS to `conductor-web` on Vercel.
- Frontend to Backend: the Next.js config rewrites `/api/v1/*` to the backend origin (`CONDUCTOR_API_ORIGIN`), so the browser stays same-origin (no CORS). Vercel forwards the request server-side to Render.
- Backend to Database: asyncpg over TLS to Neon (`CONDUCTOR_DB_URL`).
- Relay to Database: the relay drains `run_events` into the `run_view` projection over the same Neon connection.
- Backend to AI provider: outbound HTTPS with the provider key supplied as a server-side secret. The key is never exposed to the browser.

## 2. Platform selection and rejected alternatives

The prompt requires evaluating current platforms and justifying each choice on maturity, reliability, cost, developer experience, lock-in, and operational complexity, not simply picking the newest tool. Under a $0 constraint, "cost" becomes a gate rather than one factor among many: a platform is only eligible if it has a genuinely free, non-expiring tier that fits the workload.

### Frontend: Vercel Hobby (chosen)

Verified terms: free for personal, non-commercial use; roughly 100 GB bandwidth per month; a 10 second serverless function timeout; one concurrent build; automatic HTTPS; a `*.vercel.app` subdomain; and real per-pull-request preview deployments.

Rationale: Conductor's frontend is Next.js 15 App Router, which Vercel builds and hosts natively (App Router, server components, image optimization, ISR) with zero configuration. The per-PR preview deployments give us a genuine, free "staging" surface for the frontend. Automatic free SSL on the platform subdomain removes the only otherwise-unavoidable cost (a domain).

Rejected alternatives: **Cloudflare Pages** (unlimited bandwidth, strong free tier) is a valid fallback if the Vercel 100 GB bandwidth cap is ever approached, but running Next.js App Router on it is less seamless than on Vercel and would add configuration. **Netlify** is comparable but has no Next.js-native advantage. **AWS Amplify** is not free in a durable, no-credit-card sense.

Constraint to accept: the Hobby plan is non-commercial only. A portfolio or demo deployment is fine; the day the app takes payment, ads, or donations, Vercel's terms require Pro ($20/seat/month). This is a licensing limitation, not a technical one, and it is the honest boundary of "$0" for the frontend.

### Backend: Render free web service (chosen)

Verified terms: 512 MB RAM, 0.1 CPU; spins down after 15 minutes of inactivity with a 30 to 60 second cold start on the next request; 750 instance hours per month; 100 GB bandwidth; 500 build minutes per month; deploys directly from Git (no separate container registry required); no credit card.

Rationale: Conductor's backend is a persistent FastAPI process, not a set of short-lived functions, so it needs a host that runs a long-lived server. Render runs exactly this shape of workload for free, builds straight from the repo, and provides health-check wiring and automatic HTTPS on an `onrender.com` subdomain. Cold-start-on-idle is acceptable for this deployment (an explicit decision), which is precisely what makes a free backend host viable. The 750 instance-hours budget comfortably covers one service that sleeps when idle.

Rejected alternatives: **Fly.io** free allowance is now legacy and no longer a dependable no-credit-card free tier. **Railway** removed its standing free tier (trial credit only). **Koyeb** free is effectively database-only for standing workloads. **AWS App Runner / ECS / Lambda / Google Cloud Run / Azure Container Apps** either are not free in a durable sense or, in Cloud Run's case, require billing enablement and are metered; Cloud Run's scale-to-zero is attractive but the free allowance plus billing-account requirement makes it a weaker fit for a strict, no-card $0 mandate. Kubernetes (EKS/GKE/AKS/DOKS) is rejected outright: no free control plane, and vastly more operational complexity than this project warrants.

Constraint to accept: the first request after 15 minutes of idle waits 30 to 60 seconds. For a portfolio or internal tool this is tolerable; for a latency-sensitive public API it would not be. This is the core $0 tradeoff and it was accepted deliberately.

### Database: Neon free (chosen)

Verified terms: 100 CU-hours of compute per month per project, 0.5 GB storage per project, autoscaling up to 2 CU, scale-to-zero after about 5 minutes idle (cold start 500 ms to 2 s), 10 branches per project, no credit card, and no expiry (the free tier is permanent).

Rationale: managed Postgres that persists indefinitely and matches the app's existing `postgresql+asyncpg://` connection with only a connection-string swap. Scale-to-zero keeps it inside the free compute budget for a low-traffic app. Branching is the decisive feature: a branch of production is a free, isolated database, which is how we get a real "staging" database at no cost.

Rejected alternatives: **Render's own free PostgreSQL is disqualified** because it expires 30 days after creation (with a 14-day grace period) and then deletes the data. Using it would guarantee data loss, so the database is deliberately placed off Render. **Supabase** free is a valid alternative and bundles auth and storage we do not need; Neon is a cleaner fit for pure Postgres with branching. **PlanetScale** is MySQL, incompatible with our Postgres schema and migrations. **AWS RDS / Aurora / CockroachDB / MongoDB Atlas** are either not durably free or not Postgres.

Constraint to accept and manage: the 100 CU-hour monthly budget interacts with the relay cadence. See section 4 and the ledger.

### Relay worker: Render free cron job (chosen)

The relay drains the outbox into the read model. An always-on background worker would consume Render instance-hours continuously and, worse, would keep Neon permanently warm and blow the 100 CU-hour budget. Instead, the relay runs as a scheduled Render cron job (a short "drain once" invocation on an interval). This is the $0 substitute for an always-on worker.

Rejected alternatives: an always-on Render background worker (doubles instance-hour usage and defeats Neon scale-to-zero). A GitHub Actions scheduled workflow that runs the relay against the database directly is a viable no-cost alternative and is documented as a fallback; the Render cron keeps everything on one platform and closer to the app's runtime.

Constraint to accept: the read model (Insights counts) is only as fresh as the last relay tick. Cost figures and per-run data do not depend on the relay (cost reads `run_executions` directly), so the staleness is confined to aggregate insight counts. See the ledger for the cadence tradeoff.

### Supporting services (all $0)

- **DNS: Cloudflare DNS (free).** Only needed if a custom domain is added later. Default is the free platform subdomains with their automatic SSL.
- **CI/CD: GitHub Actions (free).** Unlimited minutes on public repositories; 2,000 minutes per month on private. Sufficient for lint, typecheck, tests, build, and container/security scans.
- **Security scanning (free): Dependabot, GitHub CodeQL, Trivy, and gitleaks**, all runnable in GitHub Actions at no cost (CodeQL is free for public repositories).
- **Observability (free): Sentry** (error tracking, free event allotment), **Better Stack** (log management and uptime, free tier), **UptimeRobot** (free uptime monitors), plus the built-in **Render, Vercel, and Neon dashboards** for metrics and logs. OpenTelemetry instrumentation in code is free; it is pointed at a free backend.
- **Secrets (free): GitHub Actions encrypted secrets, Vercel environment variables, and Render environment variables.** No paid secrets manager.
- **Container registry: not required.** Render builds from the Git repository, so there is no registry cost. If a registry is ever wanted, GitHub Container Registry is free for public images.

## 3. Target architecture

```
                         User (browser, HTTPS)
                                  |
                                  v
                 Vercel Hobby  (conductor-web, Next.js 15)
                 - static assets + server rendering on Vercel's edge/CDN
                 - free automatic SSL on *.vercel.app
                 - rewrites /api/v1/* server-side to the backend origin
                                  |
                                  v   (server-side proxy, same-origin to the browser)
                 Render free web service  (control-api, FastAPI/Uvicorn)
                 - sleeps after 15 min idle, 30-60s cold start on wake
                 - JWT/RBAC auth in-process
                 - health: /livez (liveness), /readyz (readiness, checks DB)
                 - outbound HTTPS to the AI provider (key server-side only)
                    |                                   ^
                    v                                   |
                 Neon free Postgres  <-----  Render free cron job (relay)
                 - scale-to-zero, TLS, no expiry         drains run_events into
                 - prod database + a branch for staging  the run_view read model
```

### Data and auth flow

- Authentication: the browser posts credentials to `/api/v1/auth/*` (proxied to the backend). The backend issues JWT access and refresh tokens; the frontend holds them in memory (mirrored to `localStorage` for dev convenience) and refreshes on 401. RBAC permission checks run in the backend on every protected route.
- API traffic: all data operations go browser to Vercel to Render to Neon. Because the frontend uses a server-side rewrite, the browser never makes a cross-origin call, so there is no CORS surface in the default configuration.
- AI calls: initiated server-side from the backend with the provider key injected as a Render secret. The key is never sent to the browser.

### Cold-start behavior (expected, by design)

The first request after an idle period pays two potential wake costs: Render (30 to 60 s) and Neon (0.5 to 2 s). After warm-up, both stay responsive until they idle again. This is the accepted consequence of the $0 constraint. A user-facing note or a lightweight "waking up" state in the frontend is recommended so the first slow load reads as intentional rather than broken.

## 4. Three environments on a $0 budget

The prompt requires separate development, staging, and production environments with no shared credentials. On free tiers this is achievable in a reduced but honest form:

- **Development**: local. Docker Compose Postgres, the backend on `:8000`, the frontend on `:3000`. This already exists in the repos.
- **Staging**:
  - Frontend: Vercel per-PR **preview deployments** (free, automatic, isolated URL per pull request). This is a genuine staging surface for the UI.
  - Database: a **Neon branch** of production (free, isolated data and connection string).
  - Backend: this is the honest gap. A second always-on Render free web service competes for the same 750 instance-hour budget. The pragmatic $0 approach is to point Vercel previews at either the production backend (read-mostly review) or a manually started second free service when actively testing backend changes, rather than pretend there is a permanently-on separate staging backend. This limitation is stated rather than hidden.
- **Production**: Vercel production deployment, one Render free web service, the Neon production database, and the Render cron relay.

Credentials never cross environments: staging uses the Neon branch's own connection string and its own secrets in Vercel/Render/GitHub environment scopes.

### The relay cadence tradeoff (a real $0 tension)

The relay keeps the Insights read model current, but running it too frequently keeps Neon permanently warm and can exceed the 100 CU-hour monthly budget. Running it rarely makes Insights counts lag. The recommended default is a moderate interval (for example, every 15 minutes) so Neon can scale to zero between drains, accepting that aggregate Insight counts can be up to one interval stale. Per-run cost and status are unaffected because they read `run_executions` directly. If fresher Insights matter more than the CU budget, shorten the interval and watch Neon usage; if the budget matters more, lengthen it or trigger the drain on demand.

## 5. Cost ledger

Every line is $0/month on the selected free tiers. The "limit / compromise" column is the honest cost paid in capability rather than dollars.

| Concern | Service | Monthly cost | Limit / compromise |
| --- | --- | --- | --- |
| Frontend hosting | Vercel Hobby | $0 | 100 GB bandwidth; non-commercial only; 10 s function timeout |
| Backend hosting | Render free web service | $0 | Sleeps after 15 min; 30-60 s cold start; 512 MB / 0.1 CPU; 750 hrs/mo |
| Background relay | Render free cron job | $0 | Runs on a schedule, not continuously; read model lags one interval |
| Database | Neon free | $0 | 0.5 GB storage; 100 CU-hours/mo; scale-to-zero wake 0.5-2 s |
| Staging (frontend) | Vercel previews | $0 | Per-PR, ephemeral |
| Staging (database) | Neon branch | $0 | Shares the free project's storage budget |
| Staging (backend) | (shared / on-demand) | $0 | No permanently-on separate staging backend |
| DNS | Cloudflare DNS | $0 | Only if a custom domain is added |
| Custom domain | (none by default) | $0 | Platform subdomains only; a domain is the one unavoidable cost if wanted |
| CI/CD | GitHub Actions | $0 | Free on public repos; 2,000 min/mo private |
| Security scanning | Dependabot, CodeQL, Trivy, gitleaks | $0 | CodeQL free on public repos |
| Error tracking | Sentry free | $0 | Capped monthly event volume |
| Logs + uptime | Better Stack free, UptimeRobot | $0 | Reduced retention and monitor counts |
| Metrics/logs (platform) | Render / Vercel / Neon dashboards | $0 | Basic; no long retention |
| Secrets | GitHub / Vercel / Render env | $0 | No dedicated secrets manager |
| AI/LLM | provider key (server-side) | usage-based | Not infrastructure; depends on provider and usage. Use a free-tier or pay-per-call key; monitor token spend |

Development, staging, and production infrastructure are each $0. The only non-infrastructure variable is AI provider usage, which is a function of the provider's own pricing and is outside the deployment platforms; it is called out so it is not mistaken for a hidden platform cost.

## 6. Explicit $0 limitations and their closest free alternatives

Stated plainly, per the cost constraint, so nothing is oversold:

- **No always-on backend.** Closest $0: Render free with cold-start-on-idle (accepted). Alternative if cold starts become unacceptable: none that is durably free for a stateful Python server; that capability requires a paid tier or a self-managed VPS.
- **No always-on worker.** Closest $0: Render cron relay on an interval, or a GitHub Actions scheduled drain. Full always-on background processing is not free here.
- **Partial staging.** Closest $0: Vercel previews plus a Neon branch cover frontend and data; the backend staging is shared or on-demand rather than a standing separate service.
- **Limited IaC coverage.** Closest $0: Terraform for Cloudflare DNS and GitHub environments/secrets (fully free and real); CLI and dashboard runbooks for Render, Neon, and Vercel, whose free tiers are not reliably provisioned via Terraform. No fake IaC will be written for resources it cannot actually create.
- **No custom domain by default.** Closest $0: free platform subdomains with automatic SSL. A domain is the single unavoidable paid item if a custom domain is required; Cloudflare DNS to point it is free.
- **No paid observability / APM.** Closest $0: Sentry, Better Stack, UptimeRobot free tiers plus platform dashboards. No distributed tracing backend beyond what these free tiers offer.
- **No HA, read replicas, or true point-in-time recovery.** Closest $0: single-instance everything, with Neon branching and a scheduled free `pg_dump` backup (to a GitHub Actions artifact) as a partial recovery substitute. Real HA and PITR are paid-tier features.

## 7. What is not claimed

This document, and the artifacts that follow, provide a complete and reproducible deployment package: configuration, CI/CD, IaC where it genuinely applies, and step-by-step commands. It does not claim the application is deployed. Deployment requires access to your Vercel, Render, Neon, Cloudflare, and GitHub accounts, which only you hold. The readiness audit at the end of the series will distinguish clearly between what has been verified in the repository (builds, configuration correctness, migration integrity) and what only you can verify by executing the steps against live accounts.

## Next in this series

2. Backend deployment artifacts: production Dockerfile, health and readiness endpoints, the Render service configuration, and the scheduled-relay cron.
3. Frontend deployment: Vercel configuration, environment wiring, and the PR-preview to production flow.
4. Database and backups: Neon setup, the production connection swap, and the free `pg_dump` backup workflow.
5. CI/CD: the three GitHub Actions workflows with free security and container scanning.
6. Infrastructure as Code: Cloudflare DNS and GitHub environments/secrets in Terraform, with CLI runbooks elsewhere.
7. Observability and security: Sentry, Better Stack, and UptimeRobot wiring, security headers, and the deployment security audit.
8. Documentation set: DEPLOYMENT.md, RUNBOOK.md, INCIDENT_RESPONSE.md, DISASTER_RECOVERY.md, ARCHITECTURE.md, and ENVIRONMENT_VARIABLES.md.
