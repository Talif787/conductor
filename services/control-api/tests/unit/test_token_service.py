from __future__ import annotations

import pytest

from app.application.auth.principal import Principal
from app.domain.identity.errors import AuthenticationError
from app.domain.identity.roles import Permission, Role
from app.domain.shared.identifiers import TenantId, UserId
from app.infrastructure.security.tokens import JwtAccessTokenService


def _service(secret: str = "test-secret-0123456789abcdef0123456789") -> JwtAccessTokenService:
    return JwtAccessTokenService(
        secret=secret,
        issuer="conductor",
        audience="conductor-api",
        ttl_seconds=900,
    )


def _principal() -> Principal:
    return Principal(user_id=UserId.new(), tenant_id=TenantId.new(), roles=frozenset({Role.OWNER}))


def test_issue_and_decode_roundtrip() -> None:
    service = _service()
    principal = _principal()
    issued = service.issue(principal)
    decoded = service.decode(issued.token)
    assert decoded.user_id == principal.user_id
    assert decoded.tenant_id == principal.tenant_id
    assert decoded.roles == principal.roles
    assert decoded.has_permission(Permission.RUNS_CANCEL)


def test_tampered_token_is_rejected() -> None:
    service = _service()
    issued = service.issue(_principal())
    tampered = issued.token[:-2] + ("aa" if not issued.token.endswith("aa") else "bb")
    with pytest.raises(AuthenticationError):
        service.decode(tampered)


def test_wrong_secret_is_rejected() -> None:
    issued = _service("secret-a-0123456789abcdef0123456789ab").issue(_principal())
    with pytest.raises(AuthenticationError):
        _service("secret-b-0123456789abcdef0123456789ab").decode(issued.token)


def test_garbage_token_is_rejected() -> None:
    with pytest.raises(AuthenticationError):
        _service().decode("not.a.jwt")
