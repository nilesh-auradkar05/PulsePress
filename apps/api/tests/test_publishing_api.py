"""Publishing API tests for the Sprint 1 content MVP."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_session
from app.main import create_app
from app.models import OutboxEvent, PostVersion


@pytest.fixture()
def client(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(
        settings,
        "local_jwt_secret",
        "test-local-jwt-secret-at-least-32-bytes",
    )
    app = create_app()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override() -> Iterator:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register(client: TestClient, name: str) -> tuple[str, dict]:
    email = f"{name.lower()}-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/local/auth/register",
        json={"email": email, "display_name": name},
    )
    assert response.status_code == 201
    body = response.json()
    return body["access_token"], body["user"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_publication(client: TestClient, token: str, handle: str) -> dict:
    response = client.post(
        "/v1/publications",
        headers=_auth(token),
        json={"handle": handle, "name": handle.title(), "description": "Test pub"},
    )
    assert response.status_code == 201
    return response.json()


def _create_post(
    client: TestClient,
    token: str,
    publication_id: str,
    *,
    title: str = "First draft",
    visibility: str = "free",
) -> dict:
    response = client.post(
        f"/v1/publications/{publication_id}/posts",
        headers=_auth(token),
        json={"title": title, "body": "Body text for the test post.", "visibility": visibility},
    )
    assert response.status_code == 201
    return response.json()


def _create_plan(
    client: TestClient,
    token: str,
    publication_id: str,
    *,
    name: str = "Supporter",
    price: int = 500,
) -> dict:
    response = client.post(
        f"/v1/publications/{publication_id}/plans",
        headers=_auth(token),
        json={"name": name, "monthly_price_cents": price},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _subscribe(
    client: TestClient,
    token: str,
    publication_id: str,
    plan_id: str,
    *,
    amount_cents: int,
) -> dict:
    response = client.post(
        "/v1/subscriptions",
        headers={**_auth(token), "Idempotency-Key": uuid.uuid4().hex},
        json={
            "publication_id": publication_id,
            "plan_id": plan_id,
            "amount_cents": amount_cents,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_publications_are_scoped_for_owner_views(client: TestClient) -> None:
    token_a, user_a = _register(client, "Ada")
    token_b, _user_b = _register(client, "Bea")
    publication = _create_publication(client, token_a, f"ada-{uuid.uuid4().hex[:8]}")

    owner_view = client.get("/v1/publications?owner=me", headers=_auth(token_a))
    assert owner_view.status_code == 200
    assert [item["id"] for item in owner_view.json()["items"]] == [publication["id"]]
    assert owner_view.json()["items"][0]["owner_user_id"] == user_a["id"]

    other_owner_view = client.get("/v1/publications?owner=me", headers=_auth(token_b))
    assert other_owner_view.status_code == 200
    assert other_owner_view.json()["items"] == []

    public_view = client.get("/v1/publications", headers=_auth(token_b))
    assert public_view.status_code == 200
    assert publication["id"] in {item["id"] for item in public_view.json()["items"]}


def test_post_mutations_are_owner_only(client: TestClient) -> None:
    token_a, _user_a = _register(client, "Owner")
    token_b, _user_b = _register(client, "Reader")
    publication = _create_publication(client, token_a, f"owner-{uuid.uuid4().hex[:8]}")
    post = _create_post(client, token_a, publication["id"])

    assert (
        client.post(
            f"/v1/publications/{publication['id']}/posts",
            headers=_auth(token_b),
            json={"title": "Nope", "body": "Nope", "visibility": "free"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/v1/publications/{publication['id']}",
            headers=_auth(token_b),
            json={"name": "Taken"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/v1/posts/{post['id']}",
            headers=_auth(token_b),
            json={"title": "Taken"},
        ).status_code
        == 403
    )
    assert client.post(f"/v1/posts/{post['id']}/publish", headers=_auth(token_b)).status_code == 403
    assert client.delete(f"/v1/posts/{post['id']}", headers=_auth(token_b)).status_code == 403


def test_publish_is_idempotent_and_creates_snapshot_and_outbox(
    client: TestClient,
    db,
) -> None:
    token, _user = _register(client, "Publisher")
    publication = _create_publication(client, token, f"pub-{uuid.uuid4().hex[:8]}")
    post = _create_post(client, token, publication["id"])

    first = client.post(f"/v1/posts/{post['id']}/publish", headers=_auth(token))
    assert first.status_code == 200
    assert first.json()["newsletter_status"] == "queued"

    second = client.post(f"/v1/posts/{post['id']}/publish", headers=_auth(token))
    assert second.status_code == 200
    assert second.json()["newsletter_status"] == "already_processed"
    assert second.json()["version_id"] == first.json()["version_id"]

    post_uuid = uuid.UUID(post["id"])
    versions = (
        db.execute(select(PostVersion).where(PostVersion.post_id == post_uuid))
        .scalars()
        .all()
    )
    events = db.execute(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_type == "post",
            OutboxEvent.aggregate_id == post_uuid,
            OutboxEvent.event_type == "post.published",
        )
    ).scalars().all()
    assert len(versions) == 1
    assert len(events) == 1


def test_paid_post_body_is_withheld_from_non_owner(client: TestClient) -> None:
    token_a, _user_a = _register(client, "Writer")
    token_b, _user_b = _register(client, "Reader")
    publication = _create_publication(client, token_a, f"paid-{uuid.uuid4().hex[:8]}")
    post = _create_post(
        client,
        token_a,
        publication["id"],
        title="Paid insight",
        visibility="paid",
    )
    assert client.post(f"/v1/posts/{post['id']}/publish", headers=_auth(token_a)).status_code == 200

    owner_read = client.get(f"/v1/posts/{post['id']}", headers=_auth(token_a))
    assert owner_read.status_code == 200
    assert owner_read.json()["entitled"] is True
    assert owner_read.json()["body"]

    reader_read = client.get(f"/v1/posts/{post['id']}", headers=_auth(token_b))
    assert reader_read.status_code == 200
    assert reader_read.json()["entitled"] is False
    assert reader_read.json()["body"] is None


def test_paid_subscription_unlocks_paid_post_body(client: TestClient) -> None:
    owner_token, _user_a = _register(client, "Writer")
    reader_token, _user_b = _register(client, "Reader")
    publication = _create_publication(client, owner_token, f"paid-sub-{uuid.uuid4().hex[:8]}")
    plan = _create_plan(client, owner_token, publication["id"], price=500)
    post = _create_post(
        client,
        owner_token,
        publication["id"],
        title="Paid insight",
        visibility="paid",
    )
    published = client.post(f"/v1/posts/{post['id']}/publish", headers=_auth(owner_token))
    assert published.status_code == 200

    _subscribe(client, reader_token, publication["id"], plan["id"], amount_cents=500)
    reader_read = client.get(f"/v1/posts/{post['id']}", headers=_auth(reader_token))

    assert reader_read.status_code == 200
    assert reader_read.json()["entitled"] is True
    assert reader_read.json()["body"] == "Body text for the test post."


def test_free_subscription_does_not_unlock_paid_post_body(client: TestClient) -> None:
    owner_token, _user_a = _register(client, "Writer")
    reader_token, _user_b = _register(client, "Reader")
    publication = _create_publication(client, owner_token, f"free-sub-{uuid.uuid4().hex[:8]}")
    free_plan = _create_plan(client, owner_token, publication["id"], name="Free", price=0)
    post = _create_post(
        client,
        owner_token,
        publication["id"],
        title="Paid insight",
        visibility="paid",
    )
    published = client.post(f"/v1/posts/{post['id']}/publish", headers=_auth(owner_token))
    assert published.status_code == 200

    _subscribe(client, reader_token, publication["id"], free_plan["id"], amount_cents=0)
    reader_read = client.get(f"/v1/posts/{post['id']}", headers=_auth(reader_token))

    assert reader_read.status_code == 200
    assert reader_read.json()["entitled"] is False
    assert reader_read.json()["body"] is None


def test_canceled_paid_subscription_retains_paid_post_access(client: TestClient) -> None:
    owner_token, _user_a = _register(client, "Writer")
    reader_token, _user_b = _register(client, "Reader")
    publication = _create_publication(client, owner_token, f"cancel-access-{uuid.uuid4().hex[:8]}")
    plan = _create_plan(client, owner_token, publication["id"], price=500)
    post = _create_post(
        client,
        owner_token,
        publication["id"],
        title="Paid insight",
        visibility="paid",
    )
    published = client.post(f"/v1/posts/{post['id']}/publish", headers=_auth(owner_token))
    assert published.status_code == 200

    subscription = _subscribe(client, reader_token, publication["id"], plan["id"], amount_cents=500)
    canceled = client.delete(
        f"/v1/subscriptions/{subscription['subscription_id']}",
        headers={**_auth(reader_token), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert canceled.status_code == 200, canceled.text

    reader_read = client.get(f"/v1/posts/{post['id']}", headers=_auth(reader_token))
    assert reader_read.status_code == 200
    assert reader_read.json()["entitled"] is True
    assert reader_read.json()["body"] == "Body text for the test post."


def test_publication_detail_embeds_plans_and_summary_counts(client: TestClient) -> None:
    owner_token, _user_a = _register(client, "Writer")
    reader_token, _user_b = _register(client, "Reader")
    publication = _create_publication(client, owner_token, f"summary-{uuid.uuid4().hex[:8]}")
    free_plan = _create_plan(client, owner_token, publication["id"], name="Free", price=0)
    paid_plan = _create_plan(client, owner_token, publication["id"], name="Supporter", price=500)
    post = _create_post(client, owner_token, publication["id"], title="Published")
    published = client.post(f"/v1/posts/{post['id']}/publish", headers=_auth(owner_token))
    assert published.status_code == 200
    _subscribe(client, reader_token, publication["id"], paid_plan["id"], amount_cents=500)

    detail = client.get(f"/v1/publications/{publication['id']}", headers=_auth(reader_token))
    assert detail.status_code == 200
    assert [plan["id"] for plan in detail.json()["active_plans"]] == [
        free_plan["id"],
        paid_plan["id"],
    ]

    summary = client.get(
        f"/v1/publications/{publication['id']}/summary",
        headers=_auth(reader_token),
    )
    assert summary.status_code == 200
    assert summary.json()["publication_id"] == publication["id"]
    assert summary.json()["subscriber_count"] == 1
    assert summary.json()["post_count"] == 1
    assert summary.json()["recent_revenue_cents"] == 500


def test_archived_post_remains_visible_to_owner_only(client: TestClient) -> None:
    token_a, _user_a = _register(client, "Archivist")
    token_b, _user_b = _register(client, "Reader")
    publication = _create_publication(client, token_a, f"archive-{uuid.uuid4().hex[:8]}")
    post = _create_post(client, token_a, publication["id"])

    archived = client.delete(f"/v1/posts/{post['id']}", headers=_auth(token_a))
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    owner_all = client.get(
        f"/v1/publications/{publication['id']}/posts",
        headers=_auth(token_a),
    )
    assert owner_all.status_code == 200
    assert post["id"] in {item["id"] for item in owner_all.json()["items"]}

    owner_archived = client.get(
        f"/v1/publications/{publication['id']}/posts?status=archived",
        headers=_auth(token_a),
    )
    assert owner_archived.status_code == 200
    assert [item["id"] for item in owner_archived.json()["items"]] == [post["id"]]

    reader_archived = client.get(
        f"/v1/publications/{publication['id']}/posts?status=archived",
        headers=_auth(token_b),
    )
    assert reader_archived.status_code == 200
    assert reader_archived.json()["items"] == []
