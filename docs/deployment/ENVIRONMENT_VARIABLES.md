# Environment Variables

Complete reference for every environment variable across the Conductor deployment. Values marked "secret" must be set in the platform's secret store (Render environment, Vercel environment variables, or GitHub Actions secrets), never committed.

## Backend (control-api, on Render)

| Variable | Required | Example / default | Purpose |
| --- | --- | --- | --- |
| `CONDUCTOR_ENVIRONMENT` | yes (prod) | `production` | Enables the production settings guard (rejects the dev auth secret). |
| `CONDUCTOR_LOG_LEVEL` | no | `INFO` | Log verbosity. |
| `WEB_CONCURRENCY` | yes (free tier) | `1` | Gunicorn worker count. Must be 1 for the in-process relay and the 512 MB tier. |
| `RUN_MIGRATIONS_ON_START` | yes | `true` | Entrypoint runs `alembic upgrade head` before serving. |
| `CONDUCTOR_EVENTS_RELAY_INPROCESS` | yes | `true` | Runs the outbox relay inside the web process (free-tier substitute for a worker). Safe only with `WEB_CONCURRENCY=1`. |
| `CONDUCTOR_EVENTS_BUS` | no | `null` | Event bus backend; `null` uses the in-process path (no Kafka). |
| `CONDUCTOR_AUTH_SECRET` | yes (prod), secret | (generated) | JWT signing secret, 32+ chars. Render generates it via the blueprint. |
| `CONDUCTOR_DB_URL` | yes, secret | `postgresql+asyncpg://user:pass@host/db` | Database URL in asyncpg form. See the two-forms note below. |
| `CONDUCTOR_DB_SSL` | yes (Neon) | `true` | Enables TLS to the database; strips libpq params asyncpg rejects. |
| `CONDUCTOR_CORS_ALLOW_ORIGINS` | no, secret | `["https://app.vercel.app"]` | JSON array of allowed origins. Leave unset with the same-origin proxy. |
| `CONDUCTOR_LLM_API_KEY` | no, secret | (unset) | AI provider key. Server-side only; unset uses the built-in fake provider. |
| `CONDUCTOR_LLM_PROVIDER` | no | `fake` | `fake` or `http`. |
| `CONDUCTOR_LLM_BASE_URL` | no | `https://api.openai.com/v1` | AI provider base URL when provider is `http`. |
| `CONDUCTOR_LLM_MODEL` | no | `conductor-default` | Model name. |
| `CONDUCTOR_OTEL_SENTRY_DSN` | no, secret | `https://key@org.ingest.sentry.io/proj` | Enables Sentry error tracking when set. |
| `CONDUCTOR_OTEL_OTLP_ENDPOINT` | no | (unset) | OpenTelemetry OTLP endpoint for tracing; off when unset. |
| `CONDUCTOR_OTEL_SERVICE_NAME` | no | `conductor-control-api` | Service name in telemetry. |

### The two URL forms (important)

The same Neon database is referenced two ways, and mixing them causes failures:

- **App / `CONDUCTOR_DB_URL`**: `postgresql+asyncpg://...` (asyncpg driver). Wrong form here produces a `psycopg2` import error at startup.
- **Backups / `NEON_DATABASE_URL` (GitHub secret)**: raw `postgresql://...?sslmode=require` (libpq). `pg_dump` speaks libpq, not asyncpg.

## Frontend (conductor-web, on Vercel)

| Variable | Required | Example | Purpose |
| --- | --- | --- | --- |
| `CONDUCTOR_API_ORIGIN` | yes | `https://conductor-api-8ioh.onrender.com` | Origin the Next rewrite proxies `/api/v1/*` to. Set in Production and Preview scopes. |

No secrets reach the frontend. The API origin is the only wiring it needs.

## CI/CD (GitHub Actions secrets, on the `conductor` repo)

| Secret | Required for | Example | Source |
| --- | --- | --- | --- |
| `NEON_DATABASE_URL` | db-backup workflow | `postgresql://...?sslmode=require` | Neon dashboard (libpq form). |
| `RENDER_DEPLOY_HOOK_URL` | orchestrated deploy (optional) | `https://api.render.com/deploy/srv-...?key=...` | Render service, Settings, Deploy Hook. |
| `PRODUCTION_API_URL` | orchestrated deploy (optional) | `https://conductor-api-8ioh.onrender.com` | The live backend URL (public, not sensitive). |
| `RENDER_STAGING_DEPLOY_HOOK_URL` | staging deploy (optional) | (staging hook) | A staging service deploy hook, if run. |
| `STAGING_API_URL` | staging smoke (optional) | (staging URL) | Staging backend URL, if run. |

## Terraform (environment, not committed)

| Variable | Required for | Purpose |
| --- | --- | --- |
| `GITHUB_TOKEN` | github provider | PAT with `repo` scope. Also read by `gh`; unset it before running `gh` to avoid auth conflicts. |
| `CLOUDFLARE_API_TOKEN` / `TF_VAR_cloudflare_api_token` | cloudflare provider | Only when `enable_dns = true`. A placeholder default lets plans run with DNS off. |

## Local development

Backend `.env` (or shell): `CONDUCTOR_DB_URL=postgresql+asyncpg://conductor:conductor@localhost:5432/conductor`, `CONDUCTOR_DB_SSL` unset (no TLS to local Postgres), `CONDUCTOR_ENVIRONMENT` unset (dev secret allowed). Frontend `.env.local`: `CONDUCTOR_API_ORIGIN=http://localhost:8000`.

Common local pitfall: stray production env vars (`CONDUCTOR_ENVIRONMENT=production`, `CONDUCTOR_DB_URL` pointing at Neon, `CONDUCTOR_DB_SSL=true`) left in a shell will make the local app connect to the wrong database or attempt TLS against local Postgres. `unset` them before local work.
