# Conductor Deployment Guide

The complete guide to deploying Conductor to production on a $0/month stack. This ties together the seven deployment slices. Companion documents: `ARCHITECTURE.md`, `ENVIRONMENT_VARIABLES.md`, `RUNBOOK.md`, `INCIDENT_RESPONSE.md`, `DISASTER_RECOVERY.md`.

## 1. Architecture

Vercel (Next.js frontend) proxies API calls to a Render free web service (FastAPI backend), which connects to a Neon free PostgreSQL database. The relay runs in-process. No Redis, Kafka, object storage, or WebSockets. See `ARCHITECTURE.md` for the full picture and the design decisions.

## 2. Prerequisites

- The two repositories: `conductor` (backend) and `conductor-web` (frontend).
- Local: Docker, Python 3.12, Node 22, the `gh` CLI, and (for IaC) Terraform.
- Accounts (all free, no card): GitHub, Vercel, Render, Neon. Optional: Sentry, Better Stack / UptimeRobot, Cloudflare (only for a custom domain).

## 3. Accounts required

| Account | Used for | Free tier |
| --- | --- | --- |
| GitHub | code, CI/CD, secrets | unlimited public / 2,000 Actions min private |
| Vercel | frontend hosting | Hobby (non-commercial), ~100 GB bandwidth |
| Render | backend hosting | free web service, 750 instance-hrs/mo |
| Neon | database | 100 CU-hrs/mo, 0.5 GB, no expiry |
| Sentry (opt) | error tracking | 5,000 errors/mo |
| Better Stack / UptimeRobot (opt) | uptime | free monitors |
| Cloudflare (opt) | DNS for a custom domain | free DNS |

## 4. Domain setup

Default: free platform subdomains (`*.vercel.app`, `*.onrender.com`) with automatic SSL. No DNS needed. A custom domain is the only unavoidable paid item (the registration); Cloudflare DNS to point it is free and defined in Terraform (`infra/terraform/cloudflare_dns.tf`, inert until `enable_dns = true`). See section 16.

## 5. Environment variables

Full reference in `ENVIRONMENT_VARIABLES.md`. The essentials: backend needs `CONDUCTOR_DB_URL` (asyncpg form), `CONDUCTOR_DB_SSL=true`, `CONDUCTOR_AUTH_SECRET` (generated), `WEB_CONCURRENCY=1`, `RUN_MIGRATIONS_ON_START=true`, `CONDUCTOR_EVENTS_RELAY_INPROCESS=true`; frontend needs `CONDUCTOR_API_ORIGIN`.

## 6. Secrets

Set via the platform stores and `gh`, never committed. Deploy-hook and backup secrets live in GitHub Actions secrets; the auth secret and DB URL in Render; the API origin in Vercel. Secrets are deliberately kept out of Terraform state.

## 7. Local setup

```bash
# backend
cd services/control-api && python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -e ".[dev]"
docker compose up -d --wait postgres && alembic upgrade head
make run   # :8000
# frontend (separate shell)
cd conductor-web && npm install && npm run dev   # :3000
```

## 8. Staging deployment

Frontend staging is automatic: every pull request gets a Vercel preview deployment. Database staging is a Neon branch of production. A standing separate staging backend is not free; point previews at production (read-mostly) or an on-demand service. The `staging.yml` workflow validates and optionally deploys if a staging hook is configured.

## 9. Production deployment

Order matters (each step needs a value from the previous):

1. **Database**: create the Neon project, copy the direct `+asyncpg` connection string (section 10).
2. **Backend**: in Render, New, Blueprint, connect `conductor` (reads `render.yaml`). Set `CONDUCTOR_DB_URL` and confirm `CONDUCTOR_DB_SSL=true`; leave CORS and the LLM key blank. Deploy. The entrypoint migrates. Note the `onrender.com` URL. Confirm `/readyz` 200.
3. **Frontend**: in Vercel, import `conductor-web`, set `CONDUCTOR_API_ORIGIN` to the backend URL (Production and Preview scopes), set Node 22, deploy.
4. Verify end to end: the production `*.vercel.app` URL renders, and sign-in works once the backend is warm.

Default deploys are Git-native: merging to `main` redeploys backend (Render) and frontend (Vercel). An orchestrated alternative with health verification is available (`production.yml`, section 18).

## 10. Database deployment

Neon, Postgres 18. Use the direct endpoint (not the pooler; asyncpg's prepared statements break under PgBouncer transaction pooling). The app URL is the `postgresql+asyncpg://` form with `CONDUCTOR_DB_SSL=true`; the backup URL is the raw libpq form. Migrations run automatically on deploy. Full detail in `04-database-neon.md`.

## 11. Redis

Not used. Conductor has no cache tier. This is intentional and removes a component that is hard to obtain for free.

## 12. Queues

Not used as a separate tier. The event path is a transactional outbox drained by the in-process relay into a Postgres read model. No Kafka.

## 13. Workers

The relay runs in-process inside the web service (`CONDUCTOR_EVENTS_RELAY_INPROCESS=true`), draining while the service is awake. No separate always-on worker (which would not be free and would keep the database warm).

## 14. Object storage

Not used. Conductor has no file uploads.

## 15. AI services

The LLM provider is called server-side from the backend with the key in `CONDUCTOR_LLM_API_KEY` (unset uses the built-in fake provider). The key never reaches the browser. AI usage is the one cost outside the free infrastructure and depends on the provider's own pricing; monitor token spend.

## 16. DNS

Default: platform subdomains, no DNS. For a custom domain: set `enable_dns = true` in Terraform with the Cloudflare zone ID and `render_hostname`, apply, then add the domain in the Vercel and Render dashboards. Records are DNS-only so the platforms' TLS works. See `06-iac.md`.

## 17. SSL

Automatic and free on all tiers (Vercel, Render, Neon). HSTS is sent by the frontend. Nothing to configure for the default subdomains.

## 18. CI/CD

`ci.yml` is the merge gate (lint, type check, unit + integration tests, Docker build). `security.yml` runs Trivy, gitleaks, and Bandit on every PR. Dependabot proposes weekly updates. `production.yml` and `staging.yml` provide optional orchestrated deploys via deploy hooks with health verification. CodeQL and environment approval gates require a public repo or a paid plan; making the repos public unlocks them free. Full detail in `05-cicd.md`.

## 19. Monitoring

Sentry for errors (set `CONDUCTOR_OTEL_SENTRY_DSN`); Better Stack / UptimeRobot for uptime (monitor the frontend freely, and `/livez` at a longer interval to avoid pinning the backend awake); platform dashboards for logs and metrics; the backend's `/metrics` for Prometheus. See `07-observability-security.md`.

## 20. Logging

The backend logs structured JSON via structlog; Render, Vercel, and Neon dashboards show logs (the free baseline). Better Stack can aggregate logs if desired.

## 21. Scaling

The free tier is single-instance with cold-start-on-idle. Vertical/horizontal scaling and always-on are paid upgrades on the same platforms; the architecture is compatible with them without rework (raise `WEB_CONCURRENCY`, move to a paid Render instance, add the Neon pooler). No changes needed to scale later.

## 22. Backups

Daily `pg_dump` to a GitHub Actions artifact (30-day retention), plus Neon branch history. Runnable on demand. See `DISASTER_RECOVERY.md`.

## 23. Disaster recovery

RPO up to 24 hours, RTO minutes. Restore procedures and a full-rebuild runbook in `DISASTER_RECOVERY.md`.

## 24. Rollback

Backend: redeploy a previous Render deploy, or revert the commit. Frontend: promote a previous Vercel deployment. A failed migration blocks the new container from serving, so the previous version keeps running. Detail in `INCIDENT_RESPONSE.md`.

## 25. Troubleshooting

Common issues and fixes are in `INCIDENT_RESPONSE.md`: `psycopg2` error (wrong DB URL scheme), auth 500 (empty/unmigrated database), cold-start slowness (expected), and CI/merge issues.

## 26. Cost optimization

Every infrastructure line is $0. The only variable cost is AI provider usage. Watch Neon CU-hours and Render instance-hours to stay within free limits; the relay cadence and uptime-monitor interval are the two knobs that most affect them.

## 27. Security

HTTPS/HSTS everywhere, security headers, JWT/RBAC with a production-secret guard, secrets in env/CLI (not in state), TLS to the database, and supply-chain scanning. The flagged gap is rate limiting on auth endpoints (the recommended next hardening). Full audit in `07-observability-security.md`.

## 28. Production checklist

- [ ] Neon database created; `CONDUCTOR_DB_URL` (+asyncpg) and `CONDUCTOR_DB_SSL=true` set in Render
- [ ] Backend deployed; `/readyz` returns 200
- [ ] `CONDUCTOR_AUTH_SECRET` set (generated); production guard satisfied
- [ ] Frontend deployed; `CONDUCTOR_API_ORIGIN` points at the backend
- [ ] End-to-end sign-in works (once warm)
- [ ] Security headers present over HTTPS; HSTS live
- [ ] CI green (quality, integration, security); Dependabot active
- [ ] Branch protection and environments applied (Terraform)
- [ ] `NEON_DATABASE_URL` secret set; backup workflow produces an artifact
- [ ] Sentry DSN set; a test error appears
- [ ] Uptime monitors on the frontend and `/livez` (sane interval)
- [ ] Deploy hook rotated if it was ever exposed
- [ ] Rate limiting on auth endpoints (recommended follow-up)
