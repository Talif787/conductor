"""Application-level ports: unit of work and event publishing."""

from __future__ import annotations

import abc
from collections.abc import Sequence
from types import TracebackType

from app.domain.run.events import DomainEvent
from app.domain.run.repository import RunRepository


class UnitOfWork(abc.ABC):
    """Transactional boundary exposing the aggregate repositories."""

    runs: RunRepository

    async def __aenter__(self) -> UnitOfWork:
        return self

    @abc.abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @abc.abstractmethod
    async def commit(self) -> None: ...

    @abc.abstractmethod
    async def rollback(self) -> None: ...


class EventPublisher(abc.ABC):
    @abc.abstractmethod
    async def publish(self, events: Sequence[DomainEvent]) -> None: ...
