"""Command handlers for the members write surface."""

from __future__ import annotations

from collections.abc import Callable

from app.application.auth.ports import PasswordHasher
from app.application.members.commands import AddMember
from app.application.members.dtos import MemberDTO
from app.application.ports import UnitOfWork
from app.domain.identity.entities import Membership, User
from app.domain.identity.errors import EmailAlreadyExistsError
from app.domain.identity.roles import Role
from app.domain.identity.value_objects import Email
from app.domain.shared.identifiers import TenantId

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
