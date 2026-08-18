# Disaster Recovery

Procedures for recovering Conductor from data loss or a full-stack rebuild. For transient failures see `INCIDENT_RESPONSE.md`.

## Recovery objectives

- **RPO (Recovery Point Objective): up to 24 hours.** The guaranteed floor is the daily `pg_dump` backup, so the maximum data lost is everything since the last nightly dump. Neon's own branch/restore history often provides a shorter effective window.
- **RTO (Recovery Time Objective): minutes.** Restoring a dump into a Neon branch takes minutes for a database this size, plus a few minutes to repoint `CONDUCTOR_DB_URL` and redeploy.

These are honest free-tier objectives. Continuous point-in-time recovery (second-level RPO) is a paid feature and is not used; the daily dump plus Neon branching is the $0 substitute.

## What is backed up

- **Database**: daily `pg_dump` (custom format) to a GitHub Actions artifact, 30-day retention, via `.github/workflows/db-backup.yml`. Also runnable on demand.
- **Code**: both repositories on GitHub (the source of truth for the app and all deployment config).
- **Infrastructure config**: `render.yaml` (backend), `vercel.json` + Vercel env (frontend), Terraform (`infra/terraform/`) for GitHub and DNS, all in Git.
- **Secrets**: NOT backed up automatically (by design, they are not in Git or state). Keep a secure record of their sources: Neon connection string, Render deploy hook, Sentry DSN, AI provider key.

## Restore the database

Restore into a fresh Neon branch first, so you never overwrite production while verifying.

```bash
# 1. download the backup artifact from the db-backup workflow run

# 2. choose a target (a new Neon branch is safest). Use the libpq URL:
export TARGET_URL="postgresql://<user>:<pass>@<host>/<db>?sslmode=require"

# 3. restore (custom-format archive, repeatable with --clean --if-exists)
pg_restore --no-owner --no-privileges --clean --if-exists -d "$TARGET_URL" conductor-<timestamp>.dump

# 4. verify
psql "$TARGET_URL" -c "\dt"                 # tables present
psql "$TARGET_URL" -c "select count(*) from users;"
```

Use a `pg_restore` (PostgreSQL client) version at least equal to the Neon server major (18). Once verified on the branch, either promote it or repoint the backend at it.

## Repoint the backend at a restored database

1. In Render, set `CONDUCTOR_DB_URL` to the restored branch's `postgresql+asyncpg://` URL (keep `CONDUCTOR_DB_SSL=true`).
2. Redeploy. The entrypoint runs `alembic upgrade head` (a no-op if already current).
3. Confirm `/readyz` is 200 and auth works.

## Full stack rebuild (from zero)

If everything is lost except the GitHub repositories:

1. **Database (Neon)**: create a new project (Postgres 18). Restore the latest backup into it (above), or start empty and let migrations create the schema on first deploy.
2. **Backend (Render)**: New, Blueprint, connect the `conductor` repo (reads `render.yaml`). Set secrets: `CONDUCTOR_DB_URL` (new Neon `+asyncpg` URL), `CONDUCTOR_DB_SSL=true`; `CONDUCTOR_AUTH_SECRET` is generated. Deploy; the entrypoint migrates. Confirm `/readyz` 200. Note the new `onrender.com` URL.
3. **Frontend (Vercel)**: import the `conductor-web` repo, set `CONDUCTOR_API_ORIGIN` to the new backend URL (Production and Preview), deploy.
4. **CI/CD and governance**: re-add GitHub secrets (`NEON_DATABASE_URL`, and deploy-hook secrets if using orchestrated deploy). Re-apply Terraform (`terraform init && terraform apply`) to restore branch protection and environments.
5. **Observability**: re-set `CONDUCTOR_OTEL_SENTRY_DSN` on Render; recreate uptime monitors.
6. **DNS** (if a custom domain was used): set `enable_dns = true` in Terraform and apply; re-add the domain in Vercel and Render.

The rebuild is reproducible because every configuration artifact lives in Git; only the secret values and the backup dump come from outside.

## DNS recovery

If a custom domain was in use and DNS is lost: the Cloudflare DNS records are defined in `infra/terraform/cloudflare_dns.tf`. Set `enable_dns = true`, provide the zone ID and Cloudflare token, and `terraform apply` recreates the apex (to Vercel) and `api` (to Render) records. Re-issue the domain in the Vercel and Render dashboards so their certificates are minted.

## Secret recovery

Secrets are intentionally not stored in Git or Terraform state. To recover them, regenerate from their sources: a new Neon connection string from the Neon dashboard, a new Render deploy hook from the service settings, a new Sentry DSN from the Sentry project, and a fresh AI provider key from the provider. Set them via the platform environment and `gh secret set`. This is why keeping a secure, out-of-band record of which secrets exist (not their values) matters.

## Testing recovery

Periodically verify the backups actually restore (a backup never tested is not a backup): download the latest artifact, restore it into a throwaway Neon branch, and confirm the row counts. Doing this once after setup and occasionally thereafter validates the whole RPO/RTO claim.
