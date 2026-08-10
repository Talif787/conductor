# Phase 2: Authentication and Tenancy

Phase 2 replaces the Phase 1 `X-Tenant-Id` header with real authentication. Every
run endpoint now derives its tenant from a validated JWT and enforces role based
permissions. The `X-Tenant-Id` examples in `PHASE1_RUNBOOK.md` are superseded by
the bearer token flow below.

## Model

Registration is self serve: it creates a tenant, an owner user, and an owner
membership in one transaction, then returns tokens. Email is globally unique and a
user has exactly one membership in this phase.

Access tokens are short lived JWTs (HS256, 15 minute default TTL). Refresh tokens
are opaque, stored only as SHA-256 hashes, and rotate on every use. Presenting a
refresh token that was already rotated or revoked is treated as compromise: the
whole token family is revoked and the request is rejected.

## Roles and permissions

| Role     | Permissions                                                  |
|----------|--------------------------------------------------------------|
| owner    | all                                                          |
| admin    | all                                                          |
| author   | runs:read, runs:create, runs:cancel, members:read           |
| operator | runs:read, runs:create, runs:cancel                         |
| viewer   | runs:read                                                   |

## Configuration

Auth is configured with the `CONDUCTOR_AUTH_` prefix. The signing secret must be
set in production; the service refuses to start in production with the default
development secret.

- `CONDUCTOR_AUTH_SECRET` (required in production)
- `CONDUCTOR_AUTH_ISSUER` (default `conductor`)
- `CONDUCTOR_AUTH_AUDIENCE` (default `conductor-api`)
- `CONDUCTOR_AUTH_ACCESS_TTL_SECONDS` (default 900)
- `CONDUCTOR_AUTH_REFRESH_TTL_SECONDS` (default 1209600)

## Endpoints

- `POST /api/v1/auth/register` creates a tenant and owner, returns tokens (201).
- `POST /api/v1/auth/login` exchanges email and password for tokens (200).
- `POST /api/v1/auth/refresh` rotates the refresh token, returns new tokens (200).
- `POST /api/v1/auth/logout` revokes the refresh token family (204).
- `GET /api/v1/auth/me` returns the current principal (200, requires a token).

## Walkthrough

Register and capture the tokens:

```bash
export BASE=http://localhost:8000
TOKENS=$(curl -s -X POST "$BASE/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"Acme","email":"owner@acme.com","password":"password123"}')
ACCESS=$(echo "$TOKENS" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
REFRESH=$(echo "$TOKENS" | python3 -c 'import sys,json; print(json.load(sys.stdin)["refresh_token"])')
```

Call a protected endpoint with the bearer token:

```bash
curl -s -X POST "$BASE/api/v1/runs" \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"goal":"Summarize the weekly report"}' | python3 -m json.tool
```

Rotate the refresh token when the access token nears expiry:

```bash
curl -s -X POST "$BASE/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}" | python3 -m json.tool
```

## Deferred to later phases

External OIDC or SSO login and JWKS validation, member invitation and email flow,
and SCIM provisioning. The token validator is issuer and audience checked, so an
external provider can be added by switching to RS256 with a JWKS key resolver
without reshaping the call sites.
