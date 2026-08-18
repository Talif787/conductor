# Runbook

Routine operational procedures for the Conductor deployment. For failures, see `INCIDENT_RESPONSE.md`; for data loss, see `DISASTER_RECOVERY.md`.

## Health checks

```bash
BACKEND=https://conductor-api-8ioh.onrender.com
curl -s -o /dev/null -w 'livez %{http_code}\n' $BACKEND/livez     # process up
curl -s -o /dev/null -w 'readyz %{http_code}\n' $BACKEND/readyz   # DB reachable
```

`/livez` returns 200 whenever the process is running. `/readyz` returns 200 only when the database is reachable. The first request after 15 minutes idle takes 30-60s while the service wakes; this is expected.

## Deployments

**Default (auto-deploy)**: merging to `main` triggers Render (backend) and Vercel (frontend) to build and deploy from Git. No manual action.

**Orchestrated (optional)**: if `production.yml` is active (autoDeploy off, deploy-hook secrets set), run:

```bash
gh workflow run production-deploy.yml   # triggers Render deploy, polls /readyz, smoke tests
gh run watch
```

**Verify a deploy landed**: check `/readyz` is 200 and the Render dashboard shows the latest commit. For the frontend, the Vercel dashboard shows the production deployment.

## Merging with branch protection

`main` requires the `quality` and `integration` checks to pass and one approving review. On a solo repo you cannot approve your own PR, so:

```bash
unset GITHUB_TOKEN                                      # if a terraform token is exported
gh pr merge <n> --squash --delete-branch --admin       # admin bypass for solo merges
```

To remove the review requirement permanently, set `required_approving_review_count = 0` in `infra/terraform/github.tf` and `terraform apply`.

## Database operations

**Run migrations manually against Neon** (normally automatic on deploy):

```bash
cd services/control-api && source ../../.venv/bin/activate
export CONDUCTOR_DB_URL="postgresql+asyncpg://<user>:<pass>@<host>/<db>"
export CONDUCTOR_DB_SSL=true
alembic upgrade head && alembic current   # expect the latest revision
```

**Check the schema exists** (guards against an empty database):

```bash
# locally, against the Docker Postgres:
docker compose exec postgres psql -U conductor -d conductor -c "\dt" | grep users
```

**Create a staging branch**: in the Neon dashboard, create a branch of production; use its `+asyncpg` URL for a preview/staging backend.

## Backups

**Trigger a manual backup**:

```bash
gh workflow run db-backup.yml
gh run watch
```

The artifact `conductor-<timestamp>.dump` appears on the workflow run, retained 30 days. Backups also run daily at 06:00 UTC. Restore is in `DISASTER_RECOVERY.md`.

## Secrets

**List / set** (values never shown):

```bash
gh secret list --repo Talif787/conductor
printf '%s' '<value>' | gh secret set <NAME> --repo Talif787/conductor
```

**Rotate the Render deploy hook** (do this if it was ever exposed): Render dashboard, service, Settings, Deploy Hook, regenerate; then re-set `RENDER_DEPLOY_HOOK_URL`.

**Rotate the auth secret**: clear `CONDUCTOR_AUTH_SECRET` in Render (it regenerates) or set a new 32+ char value; redeploy. Existing sessions invalidate.

## Observability

- **Errors**: Sentry dashboard (if `CONDUCTOR_OTEL_SENTRY_DSN` is set). Free tier is 5,000 errors/month.
- **Uptime**: Better Stack / UptimeRobot monitors on the frontend URL and `/livez`.
- **Logs / metrics**: Render, Vercel, and Neon dashboards (free baseline). The backend also exposes `/metrics` (Prometheus).

## The cold-start note

Because the backend sleeps, the first request after idle is slow and, through the Vercel proxy, may need one retry. This is normal, not an incident. Uptime monitors should ping `/livez` at a longer interval (15-30 min) so they do not pin the service awake and consume the free instance-hours.

## Routine maintenance

- **Dependabot PRs** arrive weekly. Merge when CI is green (admin bypass for solo). After merging an `upload-artifact` bump, run `db-backup.yml` once to confirm it still uploads.
- **Security scans** run on every PR (Trivy, gitleaks, Bandit). A failure is a real finding; fix or add a justified `.trivyignore` entry.
- **Monitor Neon usage** (CU-hours) and Render instance-hours in their dashboards to stay within free limits.
