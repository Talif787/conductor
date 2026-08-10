from __future__ import annotations

import uuid


def _headers(tenant_id: str) -> dict[str, str]:
    return {"X-Tenant-Id": tenant_id}


def test_create_and_get_run(client, tenant_id) -> None:
    create = client.post(
        "/api/v1/runs",
        json={"goal": "Summarize the weekly report", "priority": "high"},
        headers=_headers(tenant_id),
    )
    assert create.status_code == 201
    body = create.json()
    assert body["status"] == "queued"
    assert body["priority"] == "high"
    run_id = body["id"]

    fetched = client.get(f"/api/v1/runs/{run_id}", headers=_headers(tenant_id))
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run_id


def test_create_requires_tenant_header(client) -> None:
    resp = client.post("/api/v1/runs", json={"goal": "x"})
    assert resp.status_code == 400


def test_validation_error_returns_422(client, tenant_id) -> None:
    resp = client.post("/api/v1/runs", json={"goal": ""}, headers=_headers(tenant_id))
    assert resp.status_code == 422


def test_idempotent_create(client, tenant_id) -> None:
    headers = _headers(tenant_id) | {"Idempotency-Key": "order-42"}
    first = client.post("/api/v1/runs", json={"goal": "Reconcile"}, headers=headers)
    second = client.post("/api/v1/runs", json={"goal": "Reconcile"}, headers=headers)
    assert first.json()["id"] == second.json()["id"]


def test_list_and_cancel(client, tenant_id) -> None:
    created = client.post(
        "/api/v1/runs", json={"goal": "Backfill"}, headers=_headers(tenant_id)
    ).json()

    listing = client.get("/api/v1/runs", headers=_headers(tenant_id))
    assert listing.status_code == 200
    assert any(item["id"] == created["id"] for item in listing.json()["items"])

    cancelled = client.post(f"/api/v1/runs/{created['id']}/cancel", headers=_headers(tenant_id))
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_get_missing_run_returns_404(client, tenant_id) -> None:
    resp = client.get(f"/api/v1/runs/{uuid.uuid4()}", headers=_headers(tenant_id))
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_tenant_isolation(client) -> None:
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    created = client.post(
        "/api/v1/runs", json={"goal": "Private"}, headers=_headers(tenant_a)
    ).json()
    resp = client.get(f"/api/v1/runs/{created['id']}", headers=_headers(tenant_b))
    assert resp.status_code == 404
