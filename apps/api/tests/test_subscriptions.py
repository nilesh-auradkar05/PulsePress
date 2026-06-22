"""Subscription commerce tests (S3-T04/05/06): idempotency, guards, outbox."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    LedgerTransaction,
    OutboxEvent,
    Publication,
    Subscription,
    SubscriptionPlan,
    User,
)
from app.schemas.commerce import SubscriptionCreate
from app.services import commerce
from app.services.errors import DuplicateActiveSubscription
from tests.helpers import auth, create_plan, create_publication, idem_key, register


def _outbox(db: Session, aggregate_id: str, event_type: str) -> list[OutboxEvent]:
    return list(
        db.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == uuid.UUID(aggregate_id),
                OutboxEvent.event_type == event_type,
            )
        ).scalars()
    )


def _setup(client: TestClient, *, price: int = 500) -> tuple[str, dict, dict]:
    owner_token, _ = register(client, "Owner")
    pub = create_publication(client, owner_token)
    plan = create_plan(client, owner_token, pub["id"], monthly_price_cents=price)
    return owner_token, pub, plan


def test_paid_subscribe_returns_bill_and_writes_outbox_no_ledger(
    client: TestClient, db: Session
) -> None:
    _owner, pub, plan = _setup(client, price=500)
    sub_token, _ = register(client, "Subscriber")

    response = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tier"] == "paid"
    assert body["status"] == "active"
    assert body["bill"] == {
        "amount_cents": 500,
        "author_net_cents": 450,
        "platform_fee_cents": 50,
        "tax_cents": 40,
        "total_charged_cents": 540,
    }

    events = _outbox(db, body["subscription_id"], "subscription.created")
    assert len(events) == 1
    envelope = events[0].payload
    assert envelope["correlation_id"]
    assert envelope["payload"]["tier"] == "paid"
    assert envelope["payload"]["bill"]["total_charged_cents"] == 540
    # No ledger is written by the API (worker is Sprint 4).
    assert db.execute(select(LedgerTransaction)).scalars().all() == []


def test_free_subscribe_has_null_bill_and_outbox_no_ledger(
    client: TestClient, db: Session
) -> None:
    owner_token, pub, _paid = _setup(client, price=500)
    free_plan = create_plan(client, owner_token, pub["id"], name="Free", monthly_price_cents=0)
    sub_token, _ = register(client, "Reader")

    response = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": free_plan["id"], "amount_cents": 0},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tier"] == "free"
    assert body["bill"] is None

    events = _outbox(db, body["subscription_id"], "subscription.created")
    assert len(events) == 1
    assert events[0].payload["payload"]["bill"] is None


def test_self_subscribe_forbidden(client: TestClient) -> None:
    owner_token, pub, plan = _setup(client)
    response = client.post(
        "/v1/subscriptions",
        headers={**auth(owner_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    )
    assert response.status_code == 403


def test_amount_below_plan_minimum_rejected(client: TestClient) -> None:
    _owner, pub, plan = _setup(client, price=500)
    sub_token, _ = register(client, "Cheap")
    response = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 300},
    )
    assert response.status_code == 422


def test_duplicate_active_subscription_conflicts(client: TestClient) -> None:
    _owner, pub, plan = _setup(client)
    sub_token, _ = register(client, "Subscriber")
    first = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    )
    assert first.status_code == 201
    second = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    )
    assert second.status_code == 409


def test_missing_idempotency_key_rejected(client: TestClient) -> None:
    _owner, pub, plan = _setup(client)
    sub_token, _ = register(client, "Subscriber")
    response = client.post(
        "/v1/subscriptions",
        headers=auth(sub_token),
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    )
    assert response.status_code == 422


def test_idempotent_replay_returns_same_body_and_header(
    client: TestClient, db: Session
) -> None:
    _owner, pub, plan = _setup(client)
    sub_token, _ = register(client, "Subscriber")
    key = idem_key()
    payload = {"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500}

    headers = {**auth(sub_token), "Idempotency-Key": key}
    first = client.post("/v1/subscriptions", headers=headers, json=payload)
    assert first.status_code == 201
    second = client.post("/v1/subscriptions", headers=headers, json=payload)
    assert second.status_code == 201
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert second.json() == first.json()

    # The replay must NOT have created a second subscription or outbox event.
    events = _outbox(db, first.json()["subscription_id"], "subscription.created")
    assert len(events) == 1


def test_concurrent_same_key_subscription_does_not_double_write(engine: Engine) -> None:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    owner = User(
        cognito_sub=f"owner-{uuid.uuid4()}",
        email=f"owner-{uuid.uuid4()}@example.com",
        display_name="Owner",
    )
    subscriber = User(
        cognito_sub=f"subscriber-{uuid.uuid4()}",
        email=f"subscriber-{uuid.uuid4()}@example.com",
        display_name="Subscriber",
    )
    with factory.begin() as setup:
        setup.add_all([owner, subscriber])
        setup.flush()
        publication = Publication(
            owner_user_id=owner.id,
            handle=f"race-{uuid.uuid4().hex[:8]}",
            name="Race",
        )
        setup.add(publication)
        setup.flush()
        plan = SubscriptionPlan(
            publication_id=publication.id,
            name="Supporter",
            monthly_price_cents=500,
        )
        setup.add(plan)
        setup.flush()
        subscriber_id = subscriber.id
        publication_id = publication.id
        plan_id = plan.id

    key = idem_key()
    barrier = Barrier(2)

    def subscribe_once() -> commerce.CommerceResult:
        with factory() as session:
            user = session.get(User, subscriber_id)
            assert user is not None
            barrier.wait(timeout=5)
            return commerce.create_subscription(
                session,
                user=user,
                body=SubscriptionCreate(
                    publication_id=publication_id,
                    plan_id=plan_id,
                    amount_cents=500,
                ),
                idempotency_key=key,
                correlation_id="test",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: subscribe_once(), range(2)))

    assert [result.status_code for result in results] == [201, 201]
    assert len({result.body["subscription_id"] for result in results}) == 1
    assert sum(1 for result in results if result.replayed) == 1

    with factory() as verify:
        subscriptions = list(
            verify.execute(
                select(Subscription).where(
                    Subscription.subscriber_user_id == subscriber_id,
                    Subscription.publication_id == publication_id,
                )
            ).scalars()
        )
        assert len(subscriptions) == 1
        events = list(
            verify.execute(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "subscription",
                    OutboxEvent.aggregate_id == subscriptions[0].id,
                    OutboxEvent.event_type == "subscription.created",
                )
            ).scalars()
        )
        assert len(events) == 1


def test_concurrent_duplicate_subscription_different_keys_maps_to_conflict(
    engine: Engine,
) -> None:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    owner = User(
        cognito_sub=f"owner-{uuid.uuid4()}",
        email=f"owner-{uuid.uuid4()}@example.com",
        display_name="Owner",
    )
    subscriber = User(
        cognito_sub=f"subscriber-{uuid.uuid4()}",
        email=f"subscriber-{uuid.uuid4()}@example.com",
        display_name="Subscriber",
    )
    with factory.begin() as setup:
        setup.add_all([owner, subscriber])
        setup.flush()
        publication = Publication(
            owner_user_id=owner.id,
            handle=f"dup-race-{uuid.uuid4().hex[:8]}",
            name="Race",
        )
        setup.add(publication)
        setup.flush()
        plan = SubscriptionPlan(
            publication_id=publication.id,
            name="Supporter",
            monthly_price_cents=500,
        )
        setup.add(plan)
        setup.flush()
        subscriber_id = subscriber.id
        publication_id = publication.id
        plan_id = plan.id

    barrier = Barrier(2)

    def subscribe_once(key: str) -> commerce.CommerceResult | DuplicateActiveSubscription:
        with factory() as session:
            user = session.get(User, subscriber_id)
            assert user is not None
            barrier.wait(timeout=5)
            try:
                return commerce.create_subscription(
                    session,
                    user=user,
                    body=SubscriptionCreate(
                        publication_id=publication_id,
                        plan_id=plan_id,
                        amount_cents=500,
                    ),
                    idempotency_key=key,
                    correlation_id="test",
                )
            except DuplicateActiveSubscription as exc:
                return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(subscribe_once, [idem_key(), idem_key()]))

    assert sum(isinstance(result, commerce.CommerceResult) for result in results) == 1
    assert sum(isinstance(result, DuplicateActiveSubscription) for result in results) == 1
    with factory() as verify:
        subscriptions = list(
            verify.execute(
                select(Subscription).where(
                    Subscription.subscriber_user_id == subscriber_id,
                    Subscription.publication_id == publication_id,
                )
            ).scalars()
        )
        assert len(subscriptions) == 1


def test_same_key_different_body_conflicts(client: TestClient) -> None:
    owner_token, pub, plan = _setup(client)
    other = create_plan(client, owner_token, pub["id"], name="Bigger", monthly_price_cents=2000)
    sub_token, _ = register(client, "Subscriber")
    key = idem_key()

    first = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": key},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    )
    assert first.status_code == 201
    conflict = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": key},
        json={"publication_id": pub["id"], "plan_id": other["id"], "amount_cents": 2000},
    )
    assert conflict.status_code == 422


def test_change_tier_updates_plan_and_emits_event(client: TestClient, db: Session) -> None:
    owner_token, pub, plan = _setup(client, price=500)
    bigger = create_plan(client, owner_token, pub["id"], name="Patron", monthly_price_cents=2000)
    sub_token, _ = register(client, "Subscriber")

    created = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    ).json()
    sub_id = created["subscription_id"]

    changed = client.patch(
        f"/v1/subscriptions/{sub_id}",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"new_plan_id": bigger["id"], "new_amount_cents": 2000},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["bill"] is None  # no new ledger impact this period

    subscription = db.get(Subscription, uuid.UUID(sub_id))
    assert subscription is not None
    assert subscription.amount_cents == 2000
    assert len(_outbox(db, sub_id, "subscription.tier_changed")) == 1


def test_cancel_retains_access_and_is_no_op_on_repeat(client: TestClient, db: Session) -> None:
    _owner, pub, plan = _setup(client)
    sub_token, _ = register(client, "Subscriber")
    created = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    ).json()
    sub_id = created["subscription_id"]

    canceled = client.delete(
        f"/v1/subscriptions/{sub_id}",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
    )
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert canceled.json()["access_until"] is not None

    # A fresh later cancellation (new key) is a 200 no-op, no duplicate event.
    again = client.delete(
        f"/v1/subscriptions/{sub_id}",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
    )
    assert again.status_code == 200
    assert len(_outbox(db, sub_id, "subscription.canceled")) == 1


def test_cannot_view_another_users_subscription(client: TestClient) -> None:
    _owner, pub, plan = _setup(client)
    sub_token, _ = register(client, "Subscriber")
    other_token, _ = register(client, "Snoop")
    created = client.post(
        "/v1/subscriptions",
        headers={**auth(sub_token), "Idempotency-Key": idem_key()},
        json={"publication_id": pub["id"], "plan_id": plan["id"], "amount_cents": 500},
    ).json()

    sub_id = created["subscription_id"]
    assert client.get(f"/v1/subscriptions/{sub_id}", headers=auth(sub_token)).status_code == 200
    assert client.get(f"/v1/subscriptions/{sub_id}", headers=auth(other_token)).status_code == 403
