from __future__ import annotations


def test_livez(client) -> None:
    resp = client.get("/livez")
    assert resp.status_code == 200
    assert resp.json()["status"] == "alive"


def test_metrics_exposed(client) -> None:
    client.get("/livez")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
