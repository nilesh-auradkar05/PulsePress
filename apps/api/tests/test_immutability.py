"""Immutability tests (S2-T01) — append-only tables reject update/delete."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.immutable import ImmutableRowError
from app.models import LedgerTransaction, Post, PostVersion, Publication, User


def _balanced_tx(db: Session) -> LedgerTransaction:
    owner = User(cognito_sub=f"o-{uuid.uuid4()}", display_name="o")
    db.add(owner)
    db.flush()
    pub = Publication(owner_user_id=owner.id, handle=f"h{uuid.uuid4().hex[:10]}", name="p")
    db.add(pub)
    db.flush()
    tx = LedgerTransaction(
        publication_id=pub.id, source_type="gift", source_id=uuid.uuid4(),
        source_event_id=uuid.uuid4(), principal_amount_cents=1000, author_net_cents=900,
        platform_fee_cents=100, tax_cents=100, total_charged_cents=1100,
    )
    db.add(tx)
    db.flush()
    return tx


def test_ledger_transaction_update_blocked(db: Session) -> None:
    tx = _balanced_tx(db)
    tx.currency = "EUR"
    with pytest.raises(ImmutableRowError):
        db.flush()


def test_ledger_transaction_delete_blocked(db: Session) -> None:
    tx = _balanced_tx(db)
    db.delete(tx)
    with pytest.raises(ImmutableRowError):
        db.flush()


def test_ledger_transaction_direct_sql_update_blocked_by_database(db: Session) -> None:
    tx = _balanced_tx(db)
    with pytest.raises(DBAPIError):
        db.execute(
            text("UPDATE ledger_transactions SET currency = 'EUR' WHERE id = :id"),
            {"id": tx.id},
        )


def test_post_version_update_blocked(db: Session) -> None:
    owner = User(cognito_sub=f"o-{uuid.uuid4()}", display_name="o")
    db.add(owner)
    db.flush()
    pub = Publication(owner_user_id=owner.id, handle=f"h{uuid.uuid4().hex[:10]}", name="p")
    db.add(pub)
    db.flush()
    post = Post(publication_id=pub.id, author_user_id=owner.id, title="t", slug="t", body="b")
    db.add(post)
    db.flush()
    pv = PostVersion(post_id=post.id, title="t", body="b", visibility="free")
    db.add(pv)
    db.flush()
    pv.title = "changed"
    with pytest.raises(ImmutableRowError):
        db.flush()


def test_post_version_direct_sql_delete_blocked_by_database(db: Session) -> None:
    owner = User(cognito_sub=f"o-{uuid.uuid4()}", display_name="o")
    db.add(owner)
    db.flush()
    pub = Publication(owner_user_id=owner.id, handle=f"h{uuid.uuid4().hex[:10]}", name="p")
    db.add(pub)
    db.flush()
    post = Post(publication_id=pub.id, author_user_id=owner.id, title="t", slug="t", body="b")
    db.add(post)
    db.flush()
    pv = PostVersion(post_id=post.id, title="t", body="b", visibility="free")
    db.add(pv)
    db.flush()

    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM post_versions WHERE id = :id"), {"id": pv.id})
