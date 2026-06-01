"""Behavioral test for the internal /healthz endpoint (S1-T02).

Verifies observable HTTP behavior, not implementation internals.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(
        settings,
        "local_jwt_secret",
        "test-local-jwt-secret-at-least-32-bytes",
    )
    with TestClient(create_app()) as test_client:
        yield test_client


def test_healthz_returns_ok(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"service", "version", "status"}
    assert body["service"] == "pulsepress-api"
    assert body["status"] == "ok"
    assert isinstance(body["version"], str) and body["version"]


def test_healthz_requires_no_auth(client: TestClient) -> None:
    # No Authorization header is supplied; the probe must still succeed.
    resp = client.get("/healthz")
    assert resp.status_code == 200
