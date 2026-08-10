# Phase 1 Runbook: Conductor Control API

> Note (Phase 2): run endpoints now require a bearer token, not an
> `X-Tenant-Id` header. The header examples below are superseded by the
> auth flow in `PHASE2_AUTH.md`. Obtain a token there, then send
> `Authorization: Bearer <token>`.


This runbook covers setting up, running, testing, and verifying the Phase 1
control-plane service. It is scoped to Phase 1. When Phase 2 replaces the
`X-Tenant-Id` header with JWT authentication, the request examples here will
change.

All paths assume the repository is at `~/conductor`. The service lives at
`~/conductor/services/control-api`.

## Directory rule

Run every `make`, `docker compose`, and `alembic` command from the service
directory, because that is where the `Makefile`, `docker-compose.yml`, and
`alembic.ini` live:

```
cd ~/conductor/services/control-api
```

Git commands are the exception: run those from anywhere inside `~/conductor`.

## What Phase 1 provides

- Create, fetch, list, and cancel agent runs.
- Idempotent creation via the `Idempotency-Key` header.
- RFC 7807 problem+json error responses.
- Structured JSON logging with a per-request correlation id.
- Liveness and readiness probes, and Prometheus metrics.
- Postgres persistence of run state plus an append-only `run_events` outbox.

Tenant identity comes from an `X-Tenant-Id` header (a UUID). This is a
deliberate Phase 1 seam and is replaced by JWT-derived tenancy in Phase 2.

## 1. One-time setup

```
python3 -m venv ~/conductor/.venv        # skip if it already exists
source ~/conductor/.venv/bin/activate
make install                             # editable install plus dev tools
```

If the shell prompt loses its `(.venv)` marker after a Cloud Shell recycle,
re-run the `source` line. The virtualenv persists because it lives under
`$HOME`.

## 2. The quality gate (no database required)

This is the fast inner loop and the same gate CI runs. Tests use in-memory
adapters, so no database is needed.

```
make test        # pytest
make lint        # ruff
make typecheck   # mypy
```

Useful variations:

```
pytest -v                              # verbose, per-test names
pytest tests/unit                      # domain and handler tests only
pytest -k idempotent                   # tests matching a keyword
pytest tests/api/test_runs_api.py -v   # API tests only
```

## 3. Running the service

Pick one of three modes.

### Option A: Full stack in Docker (recommended for a real run)

Starts Postgres, applies migrations, then starts the API.

```
docker compose up --build            # foreground, Ctrl-C stops it
docker compose up --build -d         # detached, keeps your shell
docker compose ps                    # postgres, redis, migrate (exited 0), api (up)
docker compose logs -f api           # follow API logs
```

The API listens on port 8000. In Cloud Shell, use Web Preview on port 8000 and
append `/docs` to the URL. The root path has no route by design.

### Option B: Hot-reload loop (Postgres in Docker, API local)

Best while iterating on code.

```
docker compose up -d postgres
source ~/conductor/.venv/bin/activate
make migrate                         # alembic upgrade head
make run                             # uvicorn --reload on :8000
```

The default database URL points at `localhost:5432`, which matches the
Dockerized Postgres.

### Option C: No-database smoke

```
make run
```

Only `/livez`, `/docs`, `/openapi.json`, and `/metrics` respond. Run endpoints
require the database and will error. Use this only to confirm the app boots.

## 4. Exercising the API

With the service running (Option A or B), in a second shell:

```
export BASE=http://localhost:8000
export TENANT=$(python3 -c 'import uuid; print(uuid.uuid4())')
```

Create a run (expect HTTP 201, status `queued`, and a `Location` header):

```
curl -si -X POST "$BASE/api/v1/runs" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: $TENANT" \
  -d '{"goal":"Summarize the weekly report","priority":"high"}' | head -20
```

Capture an id and fetch it:

```
RUN_ID=$(curl -s -X POST "$BASE/api/v1/runs" \
  -H "Content-Type: application/json" -H "X-Tenant-Id: $TENANT" \
  -d '{"goal":"Backfill data"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

curl -s "$BASE/api/v1/runs/$RUN_ID" -H "X-Tenant-Id: $TENANT" | python3 -m json.tool
```

List, and list with a status filter:

```
curl -s "$BASE/api/v1/runs" -H "X-Tenant-Id: $TENANT" | python3 -m json.tool
curl -s "$BASE/api/v1/runs?status=queued" -H "X-Tenant-Id: $TENANT" | python3 -m json.tool
```

Idempotency (same key returns the same id both times):

```
curl -s -X POST "$BASE/api/v1/runs" -H "Content-Type: application/json" \
  -H "X-Tenant-Id: $TENANT" -H "Idempotency-Key: demo-1" \
  -d '{"goal":"Reconcile"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])'
curl -s -X POST "$BASE/api/v1/runs" -H "Content-Type: application/json" \
  -H "X-Tenant-Id: $TENANT" -H "Idempotency-Key: demo-1" \
  -d '{"goal":"Reconcile"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])'
```

Cancel (expect status `cancelled`):

```
curl -s -X POST "$BASE/api/v1/runs/$RUN_ID/cancel" -H "X-Tenant-Id: $TENANT" | python3 -m json.tool
```

Error paths:

```
# 404 problem+json
curl -s -o /dev/null -w "%{http_code}\n" \
  "$BASE/api/v1/runs/$(python3 -c 'import uuid;print(uuid.uuid4())')" \
  -H "X-Tenant-Id: $TENANT"

# 422 validation error (empty goal)
curl -s -X POST "$BASE/api/v1/runs" -H "Content-Type: application/json" \
  -H "X-Tenant-Id: $TENANT" -d '{"goal":""}' | python3 -m json.tool

# 400 missing tenant header
curl -s -X POST "$BASE/api/v1/runs" -H "Content-Type: application/json" \
  -d '{"goal":"x"}' | python3 -m json.tool
```

Tenant isolation (a different tenant gets 404):

```
OTHER=$(python3 -c 'import uuid; print(uuid.uuid4())')
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/v1/runs/$RUN_ID" -H "X-Tenant-Id: $OTHER"
```

## 5. Inspecting the database

```
docker compose exec postgres psql -U conductor -d conductor \
  -c "SELECT id, status, priority, goal FROM runs ORDER BY created_at;"

docker compose exec postgres psql -U conductor -d conductor \
  -c "SELECT name, run_id, occurred_at FROM run_events ORDER BY occurred_at;"
```

Each run should have a `RunCreated` event, and each cancelled run a
`RunCancelled` event. Seeing both tables populated confirms the foreign-key
insert ordering is correct.

## 6. Observability checks

```
curl -s "$BASE/livez"                              # {"status":"alive"}
curl -s "$BASE/readyz"                              # {"status":"ready","database":"ok"} when DB is up
curl -s "$BASE/metrics" | grep http_requests       # Prometheus counters
curl -si "$BASE/livez" | grep -i x-request-id       # correlation id echoed on responses
```

Logs are structured JSON. Each request emits one `http_request` line with
method, path, status, duration, and the `correlation_id` that ties a request to
its logs.

## 7. Stopping and cleaning up

```
docker compose down          # stop containers, keep the data volume
docker compose down -v       # stop and delete the Postgres volume (fresh start)
make down                    # shortcut for the destructive version
```

For Option B, Ctrl-C the uvicorn process first, then `docker compose down -v`.

## 8. Troubleshooting

`make: No rule to make target` or `no configuration file provided: not found`:
you are in the wrong directory. Run from `~/conductor/services/control-api`.

`readyz` returns 503 with `"database":"unavailable"`: Postgres is down or not
migrated. Run `docker compose up -d postgres` then `make migrate`.

`connection refused` on port 5432: the Postgres container is not running. Check
`docker compose ps`, start it with `docker compose up -d postgres`.

A run POST returns 500 while `/livez` is fine: you are in Option C with no
database. Switch to Option A or B.

Empty query results: no runs exist yet since the last `docker compose down -v`.
Create one first.

`docker compose` not found: try `docker-compose` (hyphen). Cloud Shell normally
ships the v2 plugin.

The `StarletteDeprecationWarning` about `httpx2` during tests is a warning, not
a failure, and is safe to ignore in Phase 1.
