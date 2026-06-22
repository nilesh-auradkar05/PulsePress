"""Plan API tests (S3-T02)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import auth, create_publication, register


def test_owner_creates_free_and_paid_plans_and_lists_them(client: TestClient) -> None:
    token, _ = register(client, "Owner")
    pub = create_publication(client, token)

    free = client.post(
        f"/v1/publications/{pub['id']}/plans",
        headers=auth(token),
        json={"name": "Free", "monthly_price_cents": 0},
    )
    assert free.status_code == 201
    assert free.json()["monthly_price_cents"] == 0
    assert free.json()["currency"] == "USD"

    paid = client.post(
        f"/v1/publications/{pub['id']}/plans",
        headers=auth(token),
        json={
            "name": "Supporter",
            "monthly_price_cents": 500,
            "allow_open_amount": True,
            "benefits": ["Members chat", "Early access"],
        },
    )
    assert paid.status_code == 201
    assert paid.json()["benefits"] == ["Members chat", "Early access"]

    listing = client.get(f"/v1/publications/{pub['id']}/plans", headers=auth(token))
    assert listing.status_code == 200
    assert {p["name"] for p in listing.json()} == {"Free", "Supporter"}


def test_non_owner_cannot_create_plan(client: TestClient) -> None:
    owner_token, _ = register(client, "Owner")
    other_token, _ = register(client, "Other")
    pub = create_publication(client, owner_token)

    response = client.post(
        f"/v1/publications/{pub['id']}/plans",
        headers=auth(other_token),
        json={"name": "Sneaky", "monthly_price_cents": 100},
    )
    assert response.status_code == 403


def test_negative_price_rejected(client: TestClient) -> None:
    token, _ = register(client, "Owner")
    pub = create_publication(client, token)
    response = client.post(
        f"/v1/publications/{pub['id']}/plans",
        headers=auth(token),
        json={"name": "Bad", "monthly_price_cents": -1},
    )
    assert response.status_code == 422


def test_non_usd_currency_rejected(client: TestClient) -> None:
    token, _ = register(client, "Owner")
    pub = create_publication(client, token)
    response = client.post(
        f"/v1/publications/{pub['id']}/plans",
        headers=auth(token),
        json={"name": "Euro", "monthly_price_cents": 100, "currency": "EUR"},
    )
    assert response.status_code == 422


def test_list_plans_for_missing_publication_is_404(client: TestClient) -> None:
    token, _ = register(client, "Owner")
    response = client.get(
        "/v1/publications/00000000-0000-0000-0000-000000000000/plans",
        headers=auth(token),
    )
    assert response.status_code == 404
