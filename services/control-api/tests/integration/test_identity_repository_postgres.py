"""Postgres-backed identity tests.

Run with a live database:  make test-integration
These verify the foreign-key insert ordering that in-memory tests cannot catch.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.auth.command_handlers import RegisterTenantHandler
from app.application.auth.commands import RegisterTenant
from app.application.auth.ports import AccessTokenService, IssuedAccessToken, PasswordHasher
from app.config.settings import get_settings
from app.domain.identity.value_objects import Email
from app.infrastructure.persistence.models import TenantModel, UserModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


class _Hasher(PasswordHasher):
    def hash(self, plaintext: str) -> str:
        return "h$" + plaintext

    def verify(self, hashed: str, plaintext: str) -> bool:
        return hashed == "h$" + plaintext


class _Tokens(AccessTokenService):
    def issue(self, principal) -> IssuedAccessToken:
        return IssuedAccessToken(token="t", expires_in_seconds=900)

    def decode(self, token):  # pragma: no cover
        raise NotImplementedError


@pytest.fixture
async def session_factory():
    engine = create_async_engine(get_settings().database.url, future=True)
    try:
        async with engine.connect():
            pass
    except Exception:  # noqa: BLE001
        await engine.dispose()
        pytest.skip("PostgreSQL is not available")
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.mark.asyncio
async def test_register_persists_identity_graph(session_factory) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    email = f"user-{uuid.uuid4().hex}@example.com"
    handler = RegisterTenantHandler(factory, _Hasher(), _Tokens(), 3600)
    tokens = await handler.handle(
        RegisterTenant(tenant_name="Acme", email=email, password="password123")
    )
    assert tokens.refresh_token

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        user = await uow.users.find_by_email(Email(email))
        assert user is not None
        memberships = await uow.memberships.find_by_user(user.id)
        assert len(memberships) == 1
        tenant_id = memberships[0].tenant_id.value
        user_id = user.id.value

    async with session_factory() as session:
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.execute(delete(TenantModel).where(TenantModel.id == tenant_id))
        await session.commit()
