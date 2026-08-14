"""Command handlers for the members write surface."""

from __future__ import annotations

from collections.abc import Callable

from app.application.auth.ports import PasswordHasher
from app.application.members.commands import AddMember, ChangeMemberRole
from app.application.members.dtos import MemberDTO
from app.application.ports import UnitOfWork
from app.domain.identity.entities import Membership, User
from app.domain.identity.errors import (
    CannotChangeOwnerRoleError,
    EmailAlreadyExistsError,
    MemberNotFoundError,
)
from app.domain.identity.roles import Role
from app.domain.identity.value_objects import Email
from app.domain.shared.identifiers import TenantId, UserId

UnitOfWorkFactory = Callable[[], UnitOfWork]


class AddMemberHandler:
    """Creates a user and a membership in an existing tenant.

    Unlike registration, this does not mint a new tenant: the member joins the
    caller's tenant with an admin-set temporary password and a chosen role.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, hasher: PasswordHasher) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher

    async def handle(self, command: AddMember) -> MemberDTO:
        email = Email(command.email)
        role = Role(command.role)
        tenant_id = TenantId.parse(command.tenant_id)
        async with self._uow_factory() as uow:
            if await uow.users.find_by_email(email) is not None:
                raise EmailAlreadyExistsError(email.value)
            user = User.create(email, self._hasher.hash(command.password))
            membership = Membership.create(user.id, tenant_id, role)
            await uow.users.add(user)
            await uow.flush()
            await uow.memberships.add(membership)
            await uow.commit()
        return MemberDTO(user_id=str(user.id), email=email.value, roles=[role.value])


class ChangeMemberRoleHandler:
    """Changes an existing member's role within the caller's tenant.

    The owner's role is immutable to avoid locking a tenant out of its own
    administration, and only non-owner roles can be assigned.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: ChangeMemberRole) -> MemberDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        user_id = UserId.parse(command.user_id)
        new_role = Role(command.role)
        async with self._uow_factory() as uow:
            memberships = await uow.memberships.find_by_user(user_id)
            membership = next((m for m in memberships if m.tenant_id == tenant_id), None)
            if membership is None:
                raise MemberNotFoundError(command.user_id)
            if membership.role == Role.OWNER:
                raise CannotChangeOwnerRoleError()
            user = await uow.users.get(user_id)
            await uow.memberships.update_role(membership.id, new_role)
            await uow.commit()
        email = user.email.value if user is not None else ""
        return MemberDTO(user_id=str(user_id), email=email, roles=[new_role.value])
