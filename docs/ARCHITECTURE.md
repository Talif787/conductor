# Conductor Code Architecture (Phase 1)

This document describes the code-level architecture as implemented. The full
system design lives in the companion Software Requirements Document and
Production Architecture Document.

## Layering and dependency rule

Four layers with dependencies pointing strictly inward:

- domain: entities, value objects, domain events, repository ports. No
  framework imports. Contains all business invariants (the Run state machine).
- application: use cases as CQRS command and query handlers, DTOs, and ports
  (UnitOfWork, EventPublisher). Depends only on domain.
- infrastructure: adapters implementing the ports (SQLAlchemy repository and
  unit of work, in-memory adapters for tests, structlog, OpenTelemetry,
  Prometheus, event publisher).
- presentation: FastAPI routers, request/response schemas, middleware, RFC 7807
  error handlers, and dependency injection providers.

Composition happens at the edge: app/main.py builds the app and app state, and
app/presentation/api/dependencies.py wires adapters into handlers via FastAPI
Depends. Nothing in domain or application imports infrastructure or presentation.

## Patterns applied

- Repository pattern: RunRepository port with SQLAlchemy and in-memory adapters.
- Unit of Work: transactional boundary that both writes commit through.
- CQRS: separate command handlers (writes) and query handlers (reads).
- Outbox seed: domain events persisted to run_events in the same transaction as
  the aggregate, ready for a Phase 6 Kafka relay.
- Aggregate with an explicit state machine: illegal transitions raise domain
  errors rather than corrupting state.

## Persistence

- runs: current state, unique (tenant_id, idempotency_key) for idempotent
  creation, composite indexes on (tenant_id, created_at) and (tenant_id, status).
- run_events: append-only domain events with a published flag for the outbox.

## Observability

- Structured JSON logs with a correlation id bound per request via contextvars.
- Prometheus counters and a latency histogram recorded in middleware, exposed
  at /metrics.
- OpenTelemetry instrumentation of FastAPI and SQLAlchemy, active only when a
  collector endpoint is configured.

## Deliberate Phase 1 scope limits

- Tenant identity is header-based (a marked seam replaced by auth in Phase 2).
- Reads use the write unit of work; a dedicated read projection arrives in
  Phase 6 with the event stream.
- Full event sourcing as the source of truth arrives in Phase 4 with the agent
  runtime; Phase 1 persists current state plus the event log.
