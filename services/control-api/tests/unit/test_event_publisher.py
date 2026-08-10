from __future__ import annotations

import uuid

import pytest

from app.domain.run.events import RunCancelled, RunCreated
from app.infrastructure.messaging.publisher import LoggingEventPublisher


@pytest.mark.asyncio
async def test_logging_publisher_emits_without_error() -> None:
    """The real publisher must not collide with structlog's reserved 'event' key.

    The API tests override the publisher with a fake, so this exercises the
    concrete LoggingEventPublisher against a real logger to catch that regression.
    """
    events = [
        RunCreated(tenant_id=uuid.uuid4(), run_id=uuid.uuid4(), goal="x", priority="normal"),
        RunCancelled(tenant_id=uuid.uuid4(), run_id=uuid.uuid4()),
    ]
    await LoggingEventPublisher().publish(events)


@pytest.mark.asyncio
async def test_logging_publisher_handles_empty() -> None:
    await LoggingEventPublisher().publish([])
