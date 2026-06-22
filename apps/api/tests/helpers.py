"""Shared helpers for API tests (local-auth register, publications, plans)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def register(client: TestClient, name: str) -> tuple[str, dict]:
    email = f"{name.lower()}-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/local/auth/register",
        json={"email": email, "display_name": name},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["access_token"], body["user"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def idem_key() -> str:
    """A fresh idempotency key (32 hex chars, comfortably over the 16 minimum)."""
    return uuid.uuid4().hex


def create_publication(client: TestClient, token: str, handle: str | None = None) -> dict:
    handle = handle or f"pub-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/v1/publications",
        headers=auth(token),
        json={"handle": handle, "name": handle.title(), "description": "Test pub"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_plan(
    client: TestClient,
    token: str,
    publication_id: str,
    *,
    name: str = "Supporter",
    monthly_price_cents: int = 500,
    allow_open_amount: bool = False,
) -> dict:
    response = client.post(
        f"/v1/publications/{publication_id}/plans",
        headers=auth(token),
        json={
            "name": name,
            "monthly_price_cents": monthly_price_cents,
            "allow_open_amount": allow_open_amount,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
