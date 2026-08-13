"""Read surface for workspace members."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.auth.principal import Principal
from app.application.members.queries import ListMembers
from app.application.members.query_handlers import ListMembersHandler
from app.domain.identity.roles import Permission
from app.presentation.api.dependencies import (
    provide_list_members_handler,
    require_permission,
)
from app.presentation.api.v1.schemas import MemberResponse

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberResponse])
async def list_members(
    principal: Annotated[Principal, Depends(require_permission(Permission.MEMBERS_READ))],
    handler: Annotated[ListMembersHandler, Depends(provide_list_members_handler)],
) -> list[MemberResponse]:
    members = await handler.handle(ListMembers(tenant_id=str(principal.tenant_id)))
    return [MemberResponse.from_dto(m) for m in members]
