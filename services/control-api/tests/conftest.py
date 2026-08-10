"""Shared pytest fixtures. API and unit tests run fully in-memory (no database)."""
from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence

import pytest
from fastapi.testclient import TestClient

from app.application.ports import EventPublisher, UnitOfWork
from app.domain.run.entities import Run
from app.domain.run.events import DomainEvent
from app.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from app.main import create_app
from app.presentation.api.dependencies import provide_publisher, provide_uow_factory


class FakePublisher(EventPublisher):
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published.extend(events)


@pytest.fixture
def store() -> dict[uuid.UUID, Run]:
    return {}


@pytest.fixture
def uow_factory(store: dict[uuid.UUID, Run]):
    def factory() -> UnitOfWork:
        return InMemoryUnitOfWork(store)

    return factory


@pytest.fixture
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
def tenant_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def client(store, uow_factory, publisher) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[provide_uow_factory] = lambda: uow_factory
    app.dependency_overrides[provide_publisher] = lambda: publisher
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
