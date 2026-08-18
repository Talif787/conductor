# Architecture

The deployed architecture of Conductor: a $0/month production stack for an agentic workflow platform. This describes what is actually running, how the pieces communicate, and the decisions behind the choices. The full platform-selection rationale is in `01-architecture-and-platform-selection.md`.

## Overview

```
                         User (browser, HTTPS)
                                  |
                                  v
                 Vercel Hobby  (conductor-web, Next.js 15)
                 - static + server rendering on Vercel's edge/CDN
                 - automatic SSL on *.vercel.app
                 - rewrites /api/v1/* server-side to CONDUCTOR_API_ORIGIN
                                  |
                                  v   (server-side proxy; same-origin to the browser)
                 Render free web service  (control-api, FastAPI/Uvicorn/Gunicorn)
                 - sleeps after 15 min idle; 30-60s cold start on wake
                 - JWT/RBAC auth in-process
                 - in-process outbox relay (drains while awake)
                 - health: /livez (liveness), /readyz (readiness, checks DB)
                 - outbound HTTPS to the AI provider (key server-side only)
                    |                          
                    v                          
                 Neon free Postgres 18 (TLS, scale-to-zero, no expiry)
                 - production database + branches for staging
                 - daily pg_dump backup to a GitHub Actions artifact
```

## Components

| Component | Technology | Host | Notes |
| --- | --- | --- | --- |
| Frontend | Next.js 15 (App Router) | Vercel Hobby | Per-PR previews; automatic SSL. |
| Backend | FastAPI / Uvicorn workers under Gunicorn | Render free web service | 512 MB, 0.1 CPU, 1 worker, sleeps on idle. |
| Relay | in-process asyncio task | (same web service) | Drains the outbox into the read model while awake. |
| Database | PostgreSQL 18 | Neon free | Scale-to-zero, TLS, no expiry, branching. |
| Auth | JWT access/refresh + RBAC | (in the backend) | Production secret guard enforced. |
| AI/LLM | provider HTTP API | (called from backend) | Key server-side only; fake provider by default. |

Deliberately not used, which is what makes $0 realistic: no Redis, no Kafka, no object storage, no WebSockets. The event path is a transactional outbox drained by the relay into a Postgres read model.

## Communication and flows

**Request path**: browser to Vercel (HTTPS) to Render (server-side rewrite, same-origin to the browser, no CORS) to Neon (asyncpg over TLS). The frontend never makes a cross-origin call in the default configuration.

**Authentication**: the browser posts credentials to `/api/v1/auth/*` (proxied). The backend issues JWT access and refresh tokens; the frontend holds them and refreshes on 401. RBAC checks run in the backend on every protected route.

**Event/read-model path**: writes emit events to a transactional outbox in the same database transaction. The in-process relay drains the outbox into the `run_view` read model. Because the relay runs inside the web process, it drains while the app is awake (which is when events are produced) and sleeps with it.

**AI calls**: initiated server-side from the backend with the provider key injected as a Render secret. The key never reaches the browser.

## Key design decisions

- **Cold-start-on-idle accepted.** The backend sleeps after 15 minutes to stay within Render's free 750 instance-hours. The first request after idle waits 30-60s. This is the core tradeoff that makes free backend hosting viable.
- **Database on Neon, not Render.** Render's free Postgres expires after 30 days; Neon's free tier is permanent. This is a structural decision, not a preference.
- **In-process relay, not a separate worker or cron.** A standing worker would keep the database warm and exceed Neon's compute budget; Render cron's free-tier status is ambiguous; frequent GitHub Actions cron would exceed private-repo minutes. Running the relay in-process is the only cleanly-free option and fits sleep-on-idle exactly.
- **Same-origin proxy, not direct CORS.** The frontend proxies to the backend so the browser stays same-origin. The tradeoff: the first request after idle is proxied through Vercel while Render wakes and may need a retry. A direct-CORS alternative is documented if smoother cold-starts are needed.
- **Migrations on start.** The container entrypoint runs `alembic upgrade head` (idempotent) so the schema is always current, avoiding reliance on a possibly-paid pre-deploy hook.

## Environments

- **Development**: local (Docker Compose Postgres, backend on :8000, frontend on :3000).
- **Staging**: Vercel per-PR previews (frontend) plus a Neon branch (database). A standing separate staging backend is not free; this is the one partial gap, stated honestly.
- **Production**: Vercel production, one Render web service, the Neon production database.

## What the architecture does not provide (honest limits)

- No high availability, read replicas, or automatic failover (single instance of each tier).
- No managed point-in-time recovery (substituted by daily `pg_dump` plus Neon branch history).
- No always-on backend (cold-start-on-idle by design).
- Custom domain is the one unavoidable paid item if wanted; the default uses free platform subdomains.

## Recovery objectives

- **RPO**: up to 24 hours (daily backup floor; Neon branch history often better).
- **RTO**: minutes (restore a dump into a Neon branch, repoint `CONDUCTOR_DB_URL`, redeploy).
