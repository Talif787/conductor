"""SQLAlchemy-backed unit of work spanning the run and identity contexts."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports import UnitOfWork
from app.infrastructure.persistence.identity_repository import (
    SqlAlchemyMembershipRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.persistence.run_repository import SqlAlchemyRunRepository
from app.infrastructure.persistence.tools_repository import SqlAlchemyToolRepository
from app.infrastructure.persistence.workflow_repository import (
    SqlAlchemyWorkflowRepository,
    SqlAlchemyWorkflowVersionRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        self.runs = SqlAlchemyRunRepository(self._session)
        self.tenants = SqlAlchemyTenantRepository(self._session)
        self.users = SqlAlchemyUserRepository(self._session)
        self.memberships = SqlAlchemyMembershipRepository(self._session)
        self.refresh_tokens = SqlAlchemyRefreshTokenRepository(self._session)
        self.tools = SqlAlchemyToolRepository(self._session)
        self.workflows = SqlAlchemyWorkflowRepository(self._session)
        self.workflow_versions = SqlAlchemyWorkflowVersionRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def flush(self) -> None:
        assert self._session is not None
        await self._session.flush()

    async def commit(self) -> None:
        assert self._session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()
