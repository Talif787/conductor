"""JWT access-token service (HS256).

The validator is issuer and audience checked, so an external OIDC provider can
be added later by switching to RS256 with a JWKS key resolver.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.application.auth.ports import AccessTokenService, IssuedAccessToken
from app.application.auth.principal import Principal
from app.domain.identity.errors import AuthenticationError
from app.domain.identity.roles import Role
from app.domain.shared.identifiers import TenantId, UserId


class JwtAccessTokenService(AccessTokenService):
    def __init__(
        self,
        *,
        secret: str,
        issuer: str,
        audience: str,
        ttl_seconds: int,
        algorithm: str = "HS256",
    ) -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._ttl = ttl_seconds
        self._algorithm = algorithm

    def issue(self, principal: Principal) -> IssuedAccessToken:
        now = datetime.now(UTC)
        payload = {
            "sub": str(principal.user_id),
            "tenant_id": str(principal.tenant_id),
            "roles": sorted(role.value for role in principal.roles),
            "iss": self._issuer,
            "aud": self._audience,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._ttl)).timestamp()),
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return IssuedAccessToken(token=token, expires_in_seconds=self._ttl)

    def decode(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("invalid access token") from exc
        try:
            return Principal(
                user_id=UserId.parse(claims["sub"]),
                tenant_id=TenantId.parse(claims["tenant_id"]),
                roles=frozenset(Role(role) for role in claims.get("roles", [])),
            )
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("malformed token claims") from exc
