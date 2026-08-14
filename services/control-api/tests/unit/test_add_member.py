"""Unit tests for adding a member to an existing tenant."""

from __future__ import annotations

import pytest

from app.application.members.command_handlers import AddMemberHandler
from app.application.members.commands import AddMember
from app.application.members.queries import ListMembers
from app.application.members.query_handlers import ListMembersHandler
from app.domain.identity.entities import Membership, Tenant, User
from app.domain.identity.errors import EmailAlreadyExistsError
from app.domain.identity.roles import Role
from app.domain.identity.value_objects import Email
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork


class _FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, hashed: str, password: str) -> bool:
        return hashed == f"hashed:{password}"


@pytest.fixture
def uow_factory():
    db = InMemoryDatabase()
    return lambda: InMemoryUnitOfWork(db)


async def _seed_owner(uow_factory) -> str:
    """Create a tenant with an owner, returning the tenant id."""
    async with uow_factory() as uow:
        tenant = Tenant.create("Acme")
        owner = User.create(Email("owner@acme.test"), "h")
        await uow.tenants.add(tenant)
        await uow.users.add(owner)
        await uow.flush()
        await uow.memberships.add(Membership.create(owner.id, tenant.id, Role.OWNER))
        await uow.commit()
        return str(tenant.id)


async def test_adds_member_to_existing_tenant(uow_factory) -> None:
    tenant_id = await _seed_owner(uow_factory)
    handler = AddMemberHandler(uow_factory, _FakeHasher())
    member = await handler.handle(
        AddMember(
            tenant_id=tenant_id,
            email="viewer@acme.test",
            password="temp-pass-123",
            role="viewer",
        )
    )
    assert member.email == "viewer@acme.test"
    assert member.roles == ["viewer"]

    # the new member shows up in the tenant roster, and no new tenant was minted
    listed = await ListMembersHandler(uow_factory).handle(ListMembers(tenant_id=tenant_id))
    emails = sorted(m.email for m in listed)
    assert emails == ["owner@acme.test", "viewer@acme.test"]


async def test_duplicate_email_is_rejected(uow_factory) -> None:
    tenant_id = await _seed_owner(uow_factory)
    handler = AddMemberHandler(uow_factory, _FakeHasher())
    with pytest.raises(EmailAlreadyExistsError):
        await handler.handle(
            AddMember(
                tenant_id=tenant_id,
                email="owner@acme.test",
                password="temp-pass-123",
                role="author",
            )
        )


async def test_member_can_log_in_with_temp_password(uow_factory) -> None:
    tenant_id = await _seed_owner(uow_factory)
    hasher = _FakeHasher()
    await AddMemberHandler(uow_factory, hasher).handle(
        AddMember(
            tenant_id=tenant_id,
            email="op@acme.test",
            password="temp-pass-123",
            role="operator",
        )
    )
    # the stored hash verifies against the temp password (login would succeed)
    async with uow_factory() as uow:
        user = await uow.users.find_by_email(Email("op@acme.test"))
    assert user is not None
    assert hasher.verify(user.password_hash, "temp-pass-123")
