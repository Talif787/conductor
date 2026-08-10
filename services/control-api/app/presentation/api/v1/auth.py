"""HTTP endpoints for authentication and tenant registration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.application.auth.command_handlers import (
    LoginHandler,
    LogoutHandler,
    RefreshTokensHandler,
    RegisterTenantHandler,
)
from app.application.auth.commands import Login, Logout, RefreshTokens, RegisterTenant
from app.application.auth.dtos import AuthTokensDTO
from app.presentation.api.dependencies import (
    CurrentPrincipal,
    provide_login_handler,
    provide_logout_handler,
    provide_refresh_handler,
    provide_register_handler,
)
from app.presentation.api.v1.schemas import (
    LoginRequest,
    PrincipalResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(dto: AuthTokensDTO) -> TokenResponse:
    return TokenResponse(
        access_token=dto.access_token,
        refresh_token=dto.refresh_token,
        token_type=dto.token_type,
        expires_in=dto.expires_in,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    handler: Annotated[RegisterTenantHandler, Depends(provide_register_handler)],
) -> TokenResponse:
    dto = await handler.handle(
        RegisterTenant(tenant_name=body.tenant_name, email=body.email, password=body.password)
    )
    return _tokens(dto)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    handler: Annotated[LoginHandler, Depends(provide_login_handler)],
) -> TokenResponse:
    dto = await handler.handle(Login(email=body.email, password=body.password))
    return _tokens(dto)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    handler: Annotated[RefreshTokensHandler, Depends(provide_refresh_handler)],
) -> TokenResponse:
    dto = await handler.handle(RefreshTokens(refresh_token=body.refresh_token))
    return _tokens(dto)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    handler: Annotated[LogoutHandler, Depends(provide_logout_handler)],
) -> None:
    await handler.handle(Logout(refresh_token=body.refresh_token))


@router.get("/me", response_model=PrincipalResponse)
async def me(principal: CurrentPrincipal) -> PrincipalResponse:
    return PrincipalResponse(
        user_id=str(principal.user_id),
        tenant_id=str(principal.tenant_id),
        roles=sorted(role.value for role in principal.roles),
        permissions=sorted(perm.value for perm in principal.permissions),
    )
