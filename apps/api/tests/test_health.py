"""Behavioral test for the internal /healthz endpoint (S1-T02).

Verifies observable HTTP behavior, not implementation internals.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_returns_ok() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"service", "version", "status"}
    assert body["service"] == "pulsepress-api"
    assert body["status"] == "ok"
    assert isinstance(body["version"], str) and body["version"]


def test_healthz_requires_no_auth() -> None:
    # No Authorization header is supplied; the probe must still succeed.
    resp = client.get("/healthz")
    assert resp.status_code == 200
