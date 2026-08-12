# Phase 8: Event-Driven CQRS (Outbox Relay, Event Bus, Read Models)

Phase 8 turns the run lifecycle events that Conductor already records into a
first-class event stream, and builds a read-optimized projection from that
stream. It adds three things: a transactional outbox relay, an event bus port
with an opt-in Kafka adapter, and a `run_view` CQRS read model served by a small
query API. None of this is on the request path: the control API keeps serving
reads and writes exactly as before, and the relay runs as a separate worker.

## Why an outbox

Since Phase 1, every run state change has been written to the `run_events` table
inside the same database transaction as the run itself. That table is a
transactional outbox: an event is persisted atomically with the state change
that produced it, so an event can never be lost because a separate publish call
failed. What was missing was a consumer. Phase 8 adds it.

## The relay worker

The relay is a standalone process:

```
make relay
# equivalently: python -m app.infrastructure.eventing.relay
```

Each pass, the relay:

1. reads a batch of unpublished `run_events` rows, oldest first (`occurred_at`, then id),
2. applies each event to the `run_view` projector, updating the read model,
3. marks those rows published,
4. commits (steps 2 and 3 are one transaction),
5. publishes the batch to the configured event bus.

Because the projection and the "mark published" update commit together, the read
model is updated exactly once per event. External publication happens after that
commit and is best-effort: if the relay crashes between the commit and the
publish, those events are already marked published and will not be re-shipped, so
external delivery is at-most-once. A stricter at-least-once external guarantee
would publish before marking, at the cost of possible re-delivery (and therefore
a projector that dedupes by event id). We chose exact read models over exact
external delivery because the read model is the primary in-process consumer; the
bus is for downstream services that can tolerate at-most-once or be upgraded to
at-least-once later. A broker failure during publish is logged and does not stop
the loop, so the read model keeps advancing even when the bus is down.

## Running the relay (single worker)

The relay is a single-worker component, like most CQRS projectors. Run one
instance. To make an accidental second instance harmless, `fetch_unpublished`
selects rows with `FOR UPDATE SKIP LOCKED`: a row being processed is locked
until that relay commits (marking it published), so another instance skips it
instead of projecting the same event twice. Without that lock, two relays race
and the second one fails with a duplicate key on the `run_view` primary key.

True horizontal scale-out of the relay (several instances sharing the load on
purpose) would additionally need the projection itself to be idempotent, for
example an upsert with `ON CONFLICT`, because events for the same run can be
locked in separate batches by different instances. That is deferred to the
Phase 11 hardening pass; the supported model today is one relay.

## The event bus port

`EventBus` (in `app/application/eventing/ports.py`) has one method,
`publish(records)`. Two adapters implement it:

- `NullEventBus` (default): logs each published record. The read model is still
  built; nothing leaves the process. This is the zero-dependency default.
- `KafkaEventBus` (opt-in): produces one JSON message per event to a topic,
  keyed by run id so a run's events land on the same partition and stay ordered.

The adapter is selected by configuration, the same opt-in-behind-a-port pattern
used for Temporal and OPA. `aiokafka` is imported lazily and is not installed by
default.

## The read model

`run_view` is a denormalized, per-run current-state table maintained only by the
projector, never by the command side. Its keys are stored as text so the read
model stays decoupled from the write schema. The projector maps each lifecycle
event to a status (`RunCreated` to `queued`, `RunCompleted` to `completed`, and
so on), tracks `event_count`, and safely ignores events it does not model. If a
status event somehow arrives before its `RunCreated` (out of order, or the create
row was pruned), the projector materializes a minimal row so the view stays
consistent.

## Query API

Both endpoints require the `RUNS_READ` permission and are tenant-scoped.

```
GET /api/v1/stats/runs
  -> { "total": 12, "active": 3, "by_status": { "completed": 8, "running": 3, "failed": 1 } }

GET /api/v1/stats/runs/recent?limit=50
  -> [ { "run_id": "...", "status": "completed", "goal": "...", "event_count": 4, ... }, ... ]
```

`active` counts runs not in a terminal status (`completed`, `failed`,
`cancelled`).

## Configuration

All settings use the `CONDUCTOR_EVENTS_` prefix.

| Setting | Env var | Default |
| --- | --- | --- |
| Bus selection | `CONDUCTOR_EVENTS_BUS` | `null` (or `kafka`) |
| Kafka brokers | `CONDUCTOR_EVENTS_KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |
| Topic | `CONDUCTOR_EVENTS_TOPIC` | `conductor.run-events` |
| Batch size | `CONDUCTOR_EVENTS_RELAY_BATCH_SIZE` | `100` |
| Poll interval (s) | `CONDUCTOR_EVENTS_RELAY_POLL_INTERVAL_SECONDS` | `1.0` |

## Metrics

The relay increments `conductor_events_published_total`, labeled by
`event_name`, for each event it publishes. The relay runs as its own process, so
scraping this counter is a deployment concern (expose a metrics port on the
worker); it is defined alongside the API metrics for consistency.

## Local demo (default bus, no Kafka)

```
docker compose up -d --wait postgres
alembic upgrade head              # applies 0007 (run_view + outbox index)

# Terminal 1: the API
make run

# Create and execute a few runs through the API so run_events fills up
# (register, create a run, execute it, and so on per the Phase 4 and 7 runbooks).

# Terminal 2: drain the outbox into the read model
make relay

# Now query the projection:
curl -H "Authorization: Bearer <token>" localhost:8000/api/v1/stats/runs
curl -H "Authorization: Bearer <token>" localhost:8000/api/v1/stats/runs/recent
```

The read model is eventually consistent: values appear once the relay has
processed the corresponding events.

## Kafka runbook (opt-in)

```
pip install -e ".[kafka]"

# A local single-broker Kafka (any standard image works), then:
export CONDUCTOR_EVENTS_BUS=kafka
export CONDUCTOR_EVENTS_KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export CONDUCTOR_EVENTS_TOPIC=conductor.run-events

make relay
# Consume the topic with your Kafka tooling of choice to see run events flow.
```

## Verification boundary

The projector and the relay drain (ordering, projection, mark-published,
batching, and resilience to a bus failure) are covered by unit tests in
`tests/unit/test_run_view_projector.py` and `tests/unit/test_outbox_relay.py`,
using an in-memory outbox, an in-memory read model, and a fake bus. The Kafka
adapter is a thin lazy-imported producer and is not exercised in CI; it is
validated manually against a real broker using the runbook above.

## What is deliberately not here

Cost tracking (per-run token and dollar accounting) is the natural next slice. It
touches the LLM gateway and the execution path rather than the event plumbing, so
it is kept separate to avoid destabilizing the tested execution flow. It will feed
the same read model and metrics surface once added.
