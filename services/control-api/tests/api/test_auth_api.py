from __future__ import annotations


def test_register_returns_tokens(client) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "Acme", "email": "owner@acme.com", "password": "password123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"] and body["refresh_token"]


def test_register_duplicate_email_conflicts(client) -> None:
    payload = {"tenant_name": "Acme", "email": "dupe@acme.com", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


def test_register_weak_password_is_rejected(client) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "Acme", "email": "weak@acme.com", "password": "short"},
    )
    assert resp.status_code == 422


def test_login_success_and_failure(client, register) -> None:
    register(email="login@acme.com", password="password123")
    ok = client.post(
        "/api/v1/auth/login", json={"email": "login@acme.com", "password": "password123"}
    )
    assert ok.status_code == 200
    bad = client.post("/api/v1/auth/login", json={"email": "login@acme.com", "password": "nope"})
    assert bad.status_code == 401


def test_me_requires_authentication(client) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_principal(client, register) -> None:
    tokens = register(email="me@acme.com")
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "owner" in body["roles"]
    assert "runs:create" in body["permissions"]


def test_refresh_rotates_and_detects_reuse(client, register) -> None:
    tokens = register(email="rotate@acme.com")
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != tokens["refresh_token"]

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401


def test_logout_then_refresh_is_rejected(client, register) -> None:
    tokens = register(email="logout@acme.com")
    assert (
        client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 204
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401
