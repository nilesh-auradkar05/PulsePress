"""Gift commerce tests (S3-T07): bill, guards, idempotency, outbox."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import GiftTransaction, LedgerTransaction, OutboxEvent, Publication, User
from app.schemas.commerce import GiftCreate
from app.services import commerce
from tests.helpers import auth, create_publication, idem_key, register


def test_send_gift_returns_bill_and_writes_outbox_no_ledger(
    client: TestClient, db: Session
) -> None:
    owner_token, _ = register(client, "Owner")
    pub = create_publication(client, owner_token)
    sender_token, _ = register(client, "Sender")

    response = client.post(
        "/v1/gifts",
        headers={**auth(sender_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "amount_cents": 1000, "message": "Loved this!"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["bill"] == {
        "amount_cents": 1000,
        "author_net_cents": 900,
        "platform_fee_cents": 100,
        "tax_cents": 80,
        "total_charged_cents": 1080,
    }

    gift_id = body["gift_id"]
    gift = db.get(GiftTransaction, uuid.UUID(gift_id))
    assert gift is not None and gift.status == "pending"

    events = list(
        db.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == uuid.UUID(gift_id),
                OutboxEvent.event_type == "gift.sent",
            )
        ).scalars()
    )
    assert len(events) == 1
    assert events[0].payload["payload"]["bill"]["total_charged_cents"] == 1080
    assert db.execute(select(LedgerTransaction)).scalars().all() == []


def test_self_gift_forbidden(client: TestClient) -> None:
    owner_token, _ = register(client, "Owner")
    pub = create_publication(client, owner_token)
    response = client.post(
        "/v1/gifts",
        headers={**auth(owner_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "amount_cents": 1000},
    )
    assert response.status_code == 403


def test_gift_below_minimum_rejected(client: TestClient) -> None:
    owner_token, _ = register(client, "Owner")
    pub = create_publication(client, owner_token)
    sender_token, _ = register(client, "Sender")
    response = client.post(
        "/v1/gifts",
        headers={**auth(sender_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "amount_cents": 49},
    )
    assert response.status_code == 422


def test_missing_idempotency_key_rejected(client: TestClient) -> None:
    owner_token, _ = register(client, "Owner")
    pub = create_publication(client, owner_token)
    sender_token, _ = register(client, "Sender")
    response = client.post(
        "/v1/gifts",
        headers=auth(sender_token),
        json={"publication_id": pub["id"], "amount_cents": 1000},
    )
    assert response.status_code == 422


def test_gift_idempotent_replay(client: TestClient, db: Session) -> None:
    owner_token, _ = register(client, "Owner")
    pub = create_publication(client, owner_token)
    sender_token, _ = register(client, "Sender")
    key = idem_key()
    payload = {"publication_id": pub["id"], "amount_cents": 1000}

    headers = {**auth(sender_token), "Idempotency-Key": key}
    first = client.post("/v1/gifts", headers=headers, json=payload)
    assert first.status_code == 201
    second = client.post("/v1/gifts", headers=headers, json=payload)
    assert second.status_code == 201
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert second.json() == first.json()

    events = list(
        db.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == uuid.UUID(first.json()["gift_id"]),
                OutboxEvent.event_type == "gift.sent",
            )
        ).scalars()
    )
    assert len(events) == 1


def test_concurrent_same_key_gift_does_not_double_write(engine: Engine) -> None:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    owner = User(
        cognito_sub=f"gift-owner-{uuid.uuid4()}",
        email=f"gift-owner-{uuid.uuid4()}@example.com",
        display_name="Owner",
    )
    sender = User(
        cognito_sub=f"gift-sender-{uuid.uuid4()}",
        email=f"gift-sender-{uuid.uuid4()}@example.com",
        display_name="Sender",
    )
    with factory.begin() as setup:
        setup.add_all([owner, sender])
        setup.flush()
        publication = Publication(
            owner_user_id=owner.id,
            handle=f"gift-race-{uuid.uuid4().hex[:8]}",
            name="Gift Race",
        )
        setup.add(publication)
        setup.flush()
        sender_id = sender.id
        publication_id = publication.id

    key = idem_key()
    barrier = Barrier(2)

    def gift_once() -> commerce.CommerceResult:
        with factory() as session:
            user = session.get(User, sender_id)
            assert user is not None
            barrier.wait(timeout=5)
            return commerce.send_gift(
                session,
                user=user,
                body=GiftCreate(publication_id=publication_id, amount_cents=1000),
                idempotency_key=key,
                correlation_id="test",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: gift_once(), range(2)))

    assert [result.status_code for result in results] == [201, 201]
    assert len({result.body["gift_id"] for result in results}) == 1
    assert sum(1 for result in results if result.replayed) == 1

    with factory() as verify:
        gifts = list(
            verify.execute(
                select(GiftTransaction).where(
                    GiftTransaction.sender_user_id == sender_id,
                    GiftTransaction.publication_id == publication_id,
                )
            ).scalars()
        )
        assert len(gifts) == 1
        events = list(
            verify.execute(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "gift",
                    OutboxEvent.aggregate_id == gifts[0].id,
                    OutboxEvent.event_type == "gift.sent",
                )
            ).scalars()
        )
        assert len(events) == 1
