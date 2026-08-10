# Conductor Control API

FastAPI control-plane service. Phase 1 implements the Run Execution bounded
context end to end: create, fetch, list, and cancel runs, with idempotency,
RFC 7807 errors, structured logging, OpenTelemetry and Prometheus wiring, and
health probes.

## Architecture

Hexagonal (ports and adapters) with DDD layering. Dependencies point inward.

```
app/
  domain/         entities, value objects, events, repository ports (pure)
  application/    commands, queries, handlers (CQRS), DTOs, ports
  infrastructure/ persistence, observability, messaging (adapters)
  presentation/   FastAPI routers, schemas, middleware, errors, DI
```

The domain layer imports no framework. Infrastructure implements the ports
declared by the domain and application layers, and is wired at the composition
root (app/main.py and app/presentation/api/dependencies.py).

## Local development

Requires Python 3.12+.

```
python -m venv .venv && source .venv/bin/activate
make install          # pip install -e ".[dev]"
make test             # unit and API tests run fully in-memory (no database)
make lint typecheck
make run              # uvicorn on :8000
```

With Docker (Postgres plus migrations plus API):

```
cp .env.example .env
make up
```

## Configuration

All configuration is read from the environment (twelve-factor). See
.env.example for the full list. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| CONDUCTOR_ENVIRONMENT | development | Deployment environment |
| CONDUCTOR_DB_URL | postgresql+asyncpg://... | Async database URL |
| CONDUCTOR_DB_POOL_SIZE | 10 | Connection pool size |
| CONDUCTOR_OTEL_OTLP_ENDPOINT | (empty) | OTLP collector endpoint; empty disables export |

## API

OpenAPI 3.1 is served at /openapi.json, interactive docs at /docs.

| Method | Path | Description |
|---|---|---|
| POST | /api/v1/runs | Create a run (supports Idempotency-Key header) |
| GET | /api/v1/runs/{id} | Fetch a run |
| GET | /api/v1/runs | List runs (status filter, keyset pagination) |
| POST | /api/v1/runs/{id}/cancel | Cancel a run |
| GET | /livez | Liveness probe |
| GET | /readyz | Readiness probe (checks the database) |
| GET | /metrics | Prometheus metrics |

Every request requires an X-Tenant-Id header in this phase. This is a temporary
seam: Phase 2 replaces it with JWT-derived tenancy behind the same dependency.

## Database

Apply migrations with `alembic upgrade head` (or the migrate compose service).
Phase 1 creates two tables: runs (current state) and run_events (append-only
outbox of domain events).

## Troubleshooting

- Tests need no database; they use in-memory adapters. If a test tries to reach
  Postgres, check that dependency overrides are applied (see tests/conftest.py).
- readyz returns 503 if the database is unreachable. Confirm CONDUCTOR_DB_URL
  and that Postgres is healthy (`docker compose ps`).
- No traces exported is expected when CONDUCTOR_OTEL_OTLP_ENDPOINT is empty.
