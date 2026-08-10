from __future__ import annotations

import uuid


def test_create_and_get_run(client, auth_headers) -> None:
    create = client.post(
        "/api/v1/runs",
        json={"goal": "Summarize the weekly report", "priority": "high"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    body = create.json()
    assert body["status"] == "queued"
    assert body["priority"] == "high"
    run_id = body["id"]

    fetched = client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run_id


def test_create_requires_authentication(client) -> None:
    resp = client.post("/api/v1/runs", json={"goal": "x"})
    assert resp.status_code == 401


def test_validation_error_returns_422(client, auth_headers) -> None:
    resp = client.post("/api/v1/runs", json={"goal": ""}, headers=auth_headers)
    assert resp.status_code == 422


def test_idempotent_create(client, auth_headers) -> None:
    headers = auth_headers | {"Idempotency-Key": "order-42"}
    first = client.post("/api/v1/runs", json={"goal": "Reconcile"}, headers=headers)
    second = client.post("/api/v1/runs", json={"goal": "Reconcile"}, headers=headers)
    assert first.json()["id"] == second.json()["id"]


def test_list_and_cancel(client, auth_headers) -> None:
    created = client.post("/api/v1/runs", json={"goal": "Backfill"}, headers=auth_headers).json()

    listing = client.get("/api/v1/runs", headers=auth_headers)
    assert listing.status_code == 200
    assert any(item["id"] == created["id"] for item in listing.json()["items"])

    cancelled = client.post(f"/api/v1/runs/{created['id']}/cancel", headers=auth_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_get_missing_run_returns_404(client, auth_headers) -> None:
    resp = client.get(f"/api/v1/runs/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_tenant_isolation(client, register) -> None:
    tenant_a = register()
    tenant_b = register()
    headers_a = {"Authorization": f"Bearer {tenant_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tenant_b['access_token']}"}

    created = client.post("/api/v1/runs", json={"goal": "Private"}, headers=headers_a).json()
    resp = client.get(f"/api/v1/runs/{created['id']}", headers=headers_b)
    assert resp.status_code == 404
