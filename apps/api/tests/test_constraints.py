"""DB constraint tests (S2-T01) — verify schema invariants reject bad writes."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    IdempotencyKey,
    LedgerEntry,
    LedgerTransaction,
    Publication,
    Subscription,
    SubscriptionPlan,
    User,
)


def _user(db: Session, sub: str) -> User:
    u = User(cognito_sub=sub, email=f"{sub}@example.com", display_name=sub)
    db.add(u)
    db.flush()
    return u


def _publication(db: Session, owner: User, handle: str) -> Publication:
    p = Publication(owner_user_id=owner.id, handle=handle, name=handle)
    db.add(p)
    db.flush()
    return p


def _plan(db: Session, pub: Publication) -> SubscriptionPlan:
    plan = SubscriptionPlan(publication_id=pub.id, name="Paid", monthly_price_cents=500)
    db.add(plan)
    db.flush()
    return plan


def test_duplicate_handle_rejected(db: Session) -> None:
    owner = _user(db, "owner-a")
    _publication(db, owner, "dup-handle")
    with pytest.raises(IntegrityError):
        _publication(db, owner, "dup-handle")


def test_duplicate_active_subscription_rejected(db: Session) -> None:
    owner = _user(db, "owner-b")
    subscriber = _user(db, "sub-b")
    pub = _publication(db, owner, "pub-b")
    plan = _plan(db, pub)
    db.add(
        Subscription(
            subscriber_user_id=subscriber.id,
            publication_id=pub.id,
            plan_id=plan.id,
            amount_cents=500,
            status="active",
        )
    )
    db.flush()
    db.add(
        Subscription(
            subscriber_user_id=subscriber.id,
            publication_id=pub.id,
            plan_id=plan.id,
            amount_cents=500,
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_canceled_subscription_does_not_trip_partial_unique(db: Session) -> None:
    owner = _user(db, "owner-c")
    subscriber = _user(db, "sub-c")
    pub = _publication(db, owner, "pub-c")
    plan = _plan(db, pub)
    # A canceled + an active row for the same (subscriber, publication) is allowed.
    db.add(
        Subscription(
            subscriber_user_id=subscriber.id, publication_id=pub.id,
            plan_id=plan.id, amount_cents=500, status="canceled",
        )
    )
    db.add(
        Subscription(
            subscriber_user_id=subscriber.id, publication_id=pub.id,
            plan_id=plan.id, amount_cents=500, status="active",
        )
    )
    db.flush()  # must not raise


def test_unbalanced_ledger_transaction_rejected(db: Session) -> None:
    owner = _user(db, "owner-d")
    pub = _publication(db, owner, "pub-d")
    # author_net + platform_fee + tax != total  -> CHECK violation
    db.add(
        LedgerTransaction(
            publication_id=pub.id,
            source_type="subscription",
            source_id=uuid.uuid4(),
            source_event_id=uuid.uuid4(),
            principal_amount_cents=1000,
            author_net_cents=900,
            platform_fee_cents=100,
            tax_cents=100,
            total_charged_cents=9999,  # wrong
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_ledger_entry_account_unique(db: Session) -> None:
    owner = _user(db, "owner-e")
    pub = _publication(db, owner, "pub-e")
    tx = LedgerTransaction(
        publication_id=pub.id,
        source_type="gift",
        source_id=uuid.uuid4(),
        source_event_id=uuid.uuid4(),
        principal_amount_cents=1000,
        author_net_cents=900,
        platform_fee_cents=100,
        tax_cents=100,
        total_charged_cents=1100,
    )
    db.add(tx)
    db.flush()
    db.add(
        LedgerEntry(
            ledger_transaction_id=tx.id, publication_id=pub.id, account="author", amount_cents=900
        )
    )
    db.flush()
    db.add(
        LedgerEntry(
            ledger_transaction_id=tx.id, publication_id=pub.id, account="author", amount_cents=1
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_idempotency_key_unique_per_user(db: Session) -> None:
    user = _user(db, "owner-f")
    db.add(IdempotencyKey(user_id=user.id, key="k1", request_hash="h"))
    db.flush()
    db.add(IdempotencyKey(user_id=user.id, key="k1", request_hash="h2"))
    with pytest.raises(IntegrityError):
        db.flush()
