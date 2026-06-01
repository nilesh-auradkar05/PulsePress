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
