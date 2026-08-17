# Deployment 4: Database on Neon ($0)

The database is managed PostgreSQL on Neon's free tier: persistent (no expiry), scale-to-zero, with branching that gives a free staging database. This document covers creating the database, the exact connection-string transformation the app needs, the SSL handling, the free backup workflow, the restore procedure, and the recovery objectives.

Neon is used instead of Render's free Postgres because Render's free database expires 30 days after creation and then deletes the data. Neon's free tier is permanent.

## Files in this slice

- `services/control-api/app/config/settings.py` (modified): adds a `CONDUCTOR_DB_SSL` flag.
- `services/control-api/app/infrastructure/persistence/session.py` (modified): strips libpq-only URL params and applies TLS via `connect_args`.
- `render.yaml` (modified): sets `CONDUCTOR_DB_SSL=true` for the deployed backend.
- `.github/workflows/db-backup.yml` (new): a free daily `pg_dump` backup to a GitHub Actions artifact.

## 1. Create the Neon database

1. Sign up at neon.tech (no credit card) and create a project. Choose PostgreSQL 17 and a region close to your Render region (for example US East to match Render Oregon is acceptable; same-continent is fine for a portfolio app).
2. Neon creates a default database and a role. From the project dashboard, open Connection Details.
3. Copy the connection string. Neon shows two forms: a direct endpoint and a pooled endpoint (its host contains `-pooler`). Copy the **direct** connection string. See section 3 for why.

Neon's connection string looks like:

```
postgresql://<user>:<password>@<endpoint>.<region>.aws.neon.tech/<db>?sslmode=require&channel_binding=require
```

## 2. The two URL forms you need

The same database is referenced two ways, and mixing them up is the most common mistake:

- **App URL (for the backend / Render `CONDUCTOR_DB_URL`)**: the SQLAlchemy + asyncpg form. Take the Neon string and change the scheme from `postgresql://` to `postgresql+asyncpg://`. You may leave the `?sslmode=require&channel_binding=require` on the end; the app strips those automatically (asyncpg does not accept them). Example:

  ```
  postgresql+asyncpg://<user>:<password>@<endpoint>.<region>.aws.neon.tech/<db>
  ```

  And set `CONDUCTOR_DB_SSL=true` so the app enables TLS via `connect_args`.

- **Backup URL (for the `NEON_DATABASE_URL` GitHub secret)**: the raw libpq form, exactly as Neon gives it, scheme `postgresql://` and keep `?sslmode=require`. `pg_dump` and `psql` understand libpq params directly. Do not use the `+asyncpg` form here.

## 3. Connection pooling: use the direct endpoint

Neon offers a pooled endpoint (PgBouncer, host with `-pooler`) and a direct endpoint. Use the **direct** endpoint for this backend, for two reasons:

- The application already manages its own connection pool through SQLAlchemy (`pool_size`, `max_overflow`, `pool_pre_ping`), so a second pooler in front adds no benefit for a single long-lived service.
- asyncpg relies on prepared statements, which break under PgBouncer transaction-pooling unless `statement_cache_size=0` is set. Using the direct endpoint avoids that pitfall entirely.

If you ever move the backend to a many-instance or serverless shape, revisit this and use the Neon pooler with `statement_cache_size=0`. For the current single free-tier service, direct is correct.

## 4. SSL handling (how the app connects securely)

Managed Postgres requires TLS. asyncpg does not accept libpq's `sslmode` or `channel_binding` as connect kwargs, so passing the Neon URL unchanged to asyncpg would raise an error. The app handles this:

- `session.py` parses the URL and removes `sslmode`, `channel_binding`, and `ssl` query params.
- When `CONDUCTOR_DB_SSL=true`, it passes `connect_args={"ssl": "require"}` to asyncpg, which encrypts the connection (matching libpq `sslmode=require`).

So the operational contract is simple: set `CONDUCTOR_DB_URL` to the `+asyncpg` form and set `CONDUCTOR_DB_SSL=true`. Locally, `CONDUCTOR_DB_SSL` stays unset (false) and the local Docker Postgres connects without TLS as before.

## 5. Wire it into the backend (Render)

In the Render service environment (from deployment slice 2), set:

| Key | Value |
| --- | --- |
| `CONDUCTOR_DB_URL` | the `postgresql+asyncpg://...` Neon direct URL |
| `CONDUCTOR_DB_SSL` | `true` |

`render.yaml` already declares `CONDUCTOR_DB_SSL=true`; you supply `CONDUCTOR_DB_URL` as the secret (it is `sync: false`). On first deploy, the container entrypoint runs `alembic upgrade head` (from slice 2), which creates the full schema in the Neon database.

## 6. Migrations against Neon

Migrations run automatically on deploy via the entrypoint (`RUN_MIGRATIONS_ON_START=true`). To run them manually from your machine against Neon (for example the first time, or to inspect state), use the app URL form with SSL:

```bash
cd services/control-api && source ../../.venv/bin/activate
export CONDUCTOR_DB_URL="postgresql+asyncpg://<user>:<password>@<endpoint>.aws.neon.tech/<db>"
export CONDUCTOR_DB_SSL=true
alembic upgrade head
alembic current      # expect 0008 (head)
```

## 7. Staging database (free, via Neon branch)

Neon branching gives a free, isolated staging database:

1. In the Neon dashboard, create a branch of the production branch (for example `staging`). It has its own endpoint and connection string and shares the project's storage budget.
2. Use that branch's `+asyncpg` URL as `CONDUCTOR_DB_URL` in your preview/staging backend environment, and its libpq URL for any staging backup.

This keeps staging data fully separate from production at no additional cost.

## 8. Backups (free daily pg_dump)

`.github/workflows/db-backup.yml` runs daily (and on demand) and stores a compressed dump as a GitHub Actions artifact for 30 days. This is the $0 substitute for managed point-in-time recovery.

Setup: add a repository secret `NEON_DATABASE_URL` set to the **libpq** Neon URL (the `postgresql://...?sslmode=require` form, not `+asyncpg`).

```
GitHub repo, Settings, Secrets and variables, Actions, New repository secret
Name:  NEON_DATABASE_URL
Value: postgresql://<user>:<password>@<endpoint>.aws.neon.tech/<db>?sslmode=require
```

The workflow installs PostgreSQL client 17 (matching the server major version so `pg_dump` does not refuse on a version mismatch), runs `pg_dump -Fc` (custom, compressed, restorable), and uploads the artifact. Trigger it once manually (Actions tab, db-backup, Run workflow) to confirm it produces an artifact.

Cost and cadence: on a private repository this is roughly 30 short runs per month, well within the free 2,000 Actions minutes. Daily gives a 24 hour worst-case data-loss window (see RPO below). Tighten to twice daily if you want a smaller window; it stays comfortably free.

## 9. Restore procedure

To restore a dump into a database (a fresh Neon branch is the safest target, so you never overwrite production while verifying):

```bash
# download the artifact from the workflow run, then:
# create/choose a target database URL (a new Neon branch is ideal)
export TARGET_URL="postgresql://<user>:<password>@<endpoint>.aws.neon.tech/<db>?sslmode=require"

pg_restore --no-owner --no-privileges --clean --if-exists \
  -d "$TARGET_URL" conductor-<timestamp>.dump
```

`--clean --if-exists` drops existing objects before recreating them, so the restore is repeatable. Verify with `psql "$TARGET_URL" -c "\dt"` and a row count on `users`. Once verified on a branch, you can point the backend at that branch or promote it.

## 10. Recovery objectives (RPO / RTO)

- **RPO (Recovery Point Objective): up to 24 hours** with the daily backup (the maximum data lost is everything since the last nightly dump). Neon's own branch/restore history provides a shorter window within its retention, so effective RPO is often better; the 24 hour figure is the guaranteed floor from the free backup alone.
- **RTO (Recovery Time Objective): minutes.** Restoring a `pg_dump` custom archive into a Neon branch takes minutes for a database this size, plus the time to repoint `CONDUCTOR_DB_URL` and redeploy (a few more minutes on Render).

These are honest free-tier objectives. Managed continuous point-in-time recovery (second-level RPO) is a paid feature and is not used here; the daily dump plus Neon branching is the $0 substitute, and it is sufficient for a portfolio or low-stakes production workload.

## 11. What is not free / not included

- No cross-region replica or automatic failover (single-instance database). If Neon has an outage, the app is down until it recovers; the backup lets you rebuild elsewhere but not fail over instantly.
- No managed PITR (paid). Substituted by daily dumps plus Neon branch history.
- Storage is capped at 0.5 GB on the free project. Ample for this schema; monitor if run/event volume grows.

## Verification (local) and live steps

Local (what can be checked without Neon):

```bash
cd services/control-api && source ../../.venv/bin/activate
make lint typecheck test          # the SSL/param-stripping change compiles and passes
# confirm the URL sanitizer drops libpq params (unit-level reasoning; asyncpg not exercised locally)
```

Live (your accounts):

1. Create the Neon project, copy the direct connection string (section 1).
2. Set `CONDUCTOR_DB_URL` (+asyncpg) and `CONDUCTOR_DB_SSL=true` in Render (section 5).
3. Deploy; confirm the entrypoint runs migrations and `/readyz` returns 200.
4. Add the `NEON_DATABASE_URL` secret and run the backup workflow once (section 8).
5. Optionally create a `staging` branch (section 7).

## What is not claimed

This provides the database configuration, the connection handling, and the backup automation. It does not create your Neon database or run a live backup; those require your Neon and GitHub accounts. The code change compiles and passes the suite; the live connection and backup are verified by you executing the steps above.
