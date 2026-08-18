# Incident Response

Diagnosis and remediation for failures in the Conductor deployment. Work top-down: confirm what is actually broken before changing anything. For routine procedures see `RUNBOOK.md`; for data loss see `DISASTER_RECOVERY.md`.

## First triage

```bash
BACKEND=https://conductor-api-8ioh.onrender.com
curl -s -o /dev/null -w 'livez %{http_code}\n' $BACKEND/livez
curl -s -o /dev/null -w 'readyz %{http_code}\n' $BACKEND/readyz
# frontend:
curl -s -o /dev/null -w 'frontend %{http_code}\n' https://conductor-web-theta.vercel.app/
```

Interpretation:
- `livez` non-200 or timing out (after allowing 60s for cold start): the backend process is down or not waking. Check Render logs and status.
- `livez` 200 but `readyz` non-200: the process is up but cannot reach the database. Go to "Database unreachable".
- Both 200 but users report errors: an application error. Check Sentry and Render logs for the specific exception.
- Frontend non-200: check the Vercel dashboard for a failed deployment.

## Backend is down (livez fails)

1. Render dashboard, the `conductor-api` service: check status and the latest deploy. A failed build leaves the previous version running or the service unhealthy.
2. If a recent deploy failed, check the build/deploy logs for the error (common: a bad migration, a missing env var). Fix and redeploy, or roll back (see Rollback).
3. If the service is sleeping and slow to wake, that is expected (30-60s), not an incident. Retry after waking.
4. Remember the free tier has 750 instance-hours/month; if exhausted, the service stops until the next month. Check Render usage.

## Database unreachable (readyz fails, livez ok)

The process is up but cannot reach Neon.

1. Check the Neon dashboard for the project status and any incident.
2. Verify `CONDUCTOR_DB_URL` in Render is the `postgresql+asyncpg://` form (not libpq, and not the pooler endpoint) and `CONDUCTOR_DB_SSL=true`.
3. A `psycopg2` import error in the logs means `CONDUCTOR_DB_URL` lost its `+asyncpg` scheme (it fell back to the sync driver). Fix the scheme and redeploy.
4. Neon scale-to-zero wake is 0.5-2s; if `readyz` is intermittently slow right after idle, that is the wake, not an outage.

## Auth returns 500 (login/register fail)

Seen during this deployment. `livez`/`readyz` can be green while auth 500s.

1. The most common cause is an empty or wrong-schema database: `relation "users" does not exist`. The app connected but the schema is missing (a fresh or recreated database that was not migrated). Fix: run `alembic upgrade head` against the correct database, or confirm `RUN_MIGRATIONS_ON_START=true` so the entrypoint migrates on deploy.
2. Confirm the app and alembic point at the same database (a stray `CONDUCTOR_DB_URL` in the environment can split them).
3. Check the backend logs for the actual traceback; the 500 body is intentionally generic.

## Frontend up but API calls fail

1. If the login page renders but authenticated actions fail with a slow spin or one-time failure, it is the backend cold-start through the Vercel proxy. Retry once the backend is warm.
2. Persistent failure: verify `CONDUCTOR_API_ORIGIN` in Vercel (Production scope) points at the live Render URL.
3. A 500 from a proxied call usually means the backend itself errored (call the backend directly to confirm) or the proxy origin is wrong.

## Error spike in Sentry

1. Open the issue in Sentry for the stack trace and the release/commit.
2. If a recent deploy caused it, roll back (see Rollback).
3. If a single bug is flooding events, the per-key rate limit (set to ~170/day) caps quota damage; the free tier drops events past 5,000/month silently, so a flood can blind you, fix the root cause promptly.

## Rollback

**Backend (Render)**: the Render dashboard lists previous deploys; select a known-good one and "Redeploy" (or "Rollback" if offered). Alternatively, revert the offending commit on `main` and let auto-deploy build the reverted state.

**Frontend (Vercel)**: the Vercel dashboard lists deployments; promote a previous good deployment to production instantly.

**Deploy succeeded but a migration failed**: the entrypoint runs migrations before serving, so a failed migration means the container does not come up healthy and the previous version keeps serving (backend stays on the last good deploy). Fix the migration and redeploy. If a migration partially applied, restore from backup (see `DISASTER_RECOVERY.md`) and re-run the corrected migration. Never leave a half-applied migration; resolve forward (fix and re-run) or backward (restore).

## CI/CD failures

- **Security job fails**: a real finding from Trivy/gitleaks/Bandit. Read the log, fix the vulnerability/secret, or add a justified `.trivyignore` entry. Do not merge past it blindly.
- **Merge blocked by required review**: solo repo; use `gh pr merge <n> --squash --delete-branch --admin`.
- **`gh` "Resource not accessible by personal access token"**: a terraform `GITHUB_TOKEN` is shadowing your login. `unset GITHUB_TOKEN` and retry.

## Escalation and dependency outages

This is a $0 single-instance stack; there is no failover. If a platform (Render, Neon, or Vercel) has an outage, the affected tier is down until the platform recovers. Expected behavior per dependency:

- **Neon down**: the backend serves `livez` but `readyz` fails and data operations error. Wait for Neon, or restore the latest backup into a new database/provider and repoint `CONDUCTOR_DB_URL`.
- **Render down**: the backend is unreachable; the frontend static shell still loads but API calls fail. Wait for Render, or deploy the container elsewhere.
- **Vercel down**: the frontend is unreachable; the backend API still responds directly.

Check each platform's status page during an incident before assuming a configuration problem.
