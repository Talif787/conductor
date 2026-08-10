"""Shared pytest fixtures. Unit and API tests run fully in-memory (no database)."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Callable, Iterator, Sequence

import pytest
from fastapi.testclient import TestClient

from app.application.auth.ports import AccessTokenService, IssuedAccessToken, PasswordHasher
from app.application.auth.principal import Principal
from app.application.ports import EventPublisher, UnitOfWork
from app.domain.identity.errors import AuthenticationError
from app.domain.identity.roles import Role
from app.domain.run.events import DomainEvent
from app.domain.shared.identifiers import TenantId, UserId
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork
from app.main import create_app
from app.presentation.api.dependencies import (
    provide_password_hasher,
    provide_publisher,
    provide_token_service,
    provide_uow_factory,
)


class FakePublisher(EventPublisher):
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published.extend(events)


class FakeHasher(PasswordHasher):
    def hash(self, plaintext: str) -> str:
        return "fake$" + plaintext

    def verify(self, hashed: str, plaintext: str) -> bool:
        return hashed == "fake$" + plaintext


class FakeTokenService(AccessTokenService):
    """Reversible, unsigned encoding of the principal. For tests only."""

    def issue(self, principal: Principal) -> IssuedAccessToken:
        payload = {
            "sub": str(principal.user_id),
            "tenant_id": str(principal.tenant_id),
            "roles": sorted(role.value for role in principal.roles),
        }
        token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        return IssuedAccessToken(token=token, expires_in_seconds=900)

    def decode(self, token: str) -> Principal:
        try:
            data = json.loads(base64.urlsafe_b64decode(token.encode()))
            return Principal(
                user_id=UserId.parse(data["sub"]),
                tenant_id=TenantId.parse(data["tenant_id"]),
                roles=frozenset(Role(role) for role in data["roles"]),
            )
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationError("invalid token") from exc


@pytest.fixture
def db() -> InMemoryDatabase:
    return InMemoryDatabase()


@pytest.fixture
def uow_factory(db: InMemoryDatabase) -> Callable[[], UnitOfWork]:
    return lambda: InMemoryUnitOfWork(db)


@pytest.fixture
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
def hasher() -> FakeHasher:
    return FakeHasher()


@pytest.fixture
def token_service() -> FakeTokenService:
    return FakeTokenService()


@pytest.fixture
def client(uow_factory, publisher, hasher, token_service) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[provide_uow_factory] = lambda: uow_factory
    app.dependency_overrides[provide_publisher] = lambda: publisher
    app.dependency_overrides[provide_password_hasher] = lambda: hasher
    app.dependency_overrides[provide_token_service] = lambda: token_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def register(client: TestClient) -> Callable[..., dict]:
    def _register(
        email: str | None = None,
        tenant_name: str = "Acme",
        password: str = "password123",
    ) -> dict:
        payload = {
            "tenant_name": tenant_name,
            "email": email or f"user-{uuid.uuid4().hex}@example.com",
            "password": password,
        }
        resp = client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _register


@pytest.fixture
def auth_headers(register: Callable[..., dict]) -> dict[str, str]:
    tokens = register()
    return {"Authorization": f"Bearer {tokens['access_token']}"}
