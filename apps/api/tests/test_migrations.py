"""Migration roundtrip test (S2-T01) — alembic upgrade head then downgrade base.

Runs against a disposable sibling database derived from ``TEST_DATABASE_URL`` so
it does not disturb the metadata-built schema used by the other DB tests.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture()
def mig_db_url() -> Iterator[str]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    base, dbname = TEST_DATABASE_URL.rsplit("/", 1)
    mig_name = f"{dbname}_mig"
    admin_url = f"{base}/postgres"

    def _admin(stmt: str) -> None:
        eng = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
        with eng.connect() as conn:
            conn.execute(text(stmt))
        eng.dispose()

    _admin(f'DROP DATABASE IF EXISTS "{mig_name}"')
    _admin(f'CREATE DATABASE "{mig_name}"')
    yield f"{base}/{mig_name}"
    _admin(f'DROP DATABASE IF EXISTS "{mig_name}"')


def _cfg(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _base_tables(url: str) -> list[str]:
    eng = create_engine(url, future=True)
    try:
        with eng.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE'"
                )
            )
            return [r[0] for r in rows]
    finally:
        eng.dispose()


def test_upgrade_then_downgrade(mig_db_url: str) -> None:
    cfg = _cfg(mig_db_url)

    command.upgrade(cfg, "head")
    tables = _base_tables(mig_db_url)
    assert "users" in tables
    assert "ledger_transactions" in tables
    assert len([t for t in tables if t != "alembic_version"]) == 17

    command.downgrade(cfg, "base")
    tables_after = _base_tables(mig_db_url)
    assert "users" not in tables_after
    assert "ledger_transactions" not in tables_after


def test_ledger_transaction_requires_the_complete_three_entry_set(mig_db_url: str) -> None:
    cfg = _cfg(mig_db_url)
    command.upgrade(cfg, "head")
    engine = create_engine(mig_db_url, future=True)
    owner_id = uuid.uuid4()
    publication_id = uuid.uuid4()
    invalid_transaction_id = uuid.uuid4()

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, cognito_sub, email, display_name, is_admin) "
                    "VALUES (:id, :sub, :email, :name, false)"
                ),
                {
                    "id": owner_id,
                    "sub": "migration-ledger-owner",
                    "email": "owner@example.com",
                    "name": "Owner",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO publications (id, owner_user_id, handle, name, is_active) "
                    "VALUES (:id, :owner_id, :handle, :name, true)"
                ),
                {
                    "id": publication_id,
                    "owner_id": owner_id,
                    "handle": "migration-ledger",
                    "name": "Migration Ledger",
                },
            )

        connection = engine.connect()
        transaction = connection.begin()
        connection.execute(
            text(
                "INSERT INTO ledger_transactions "
                "(id, publication_id, source_type, source_id, source_event_id, "
                "principal_amount_cents, author_net_cents, platform_fee_cents, tax_cents, "
                "total_charged_cents, currency) "
                "VALUES (:id, :publication_id, 'gift', :source_id, :event_id, "
                "1000, 900, 100, 80, 1080, 'USD')"
            ),
            {
                "id": invalid_transaction_id,
                "publication_id": publication_id,
                "source_id": uuid.uuid4(),
                "event_id": uuid.uuid4(),
            },
        )
        connection.execute(
            text(
                "INSERT INTO ledger_entries "
                "(id, ledger_transaction_id, publication_id, account, amount_cents, direction) "
                "VALUES (:id, :transaction_id, :publication_id, 'author', 900, 'credit')"
            ),
            {
                "id": uuid.uuid4(),
                "transaction_id": invalid_transaction_id,
                "publication_id": publication_id,
            },
        )
        with pytest.raises(IntegrityError, match="exactly three balanced entries"):
            transaction.commit()
        connection.close()
    finally:
        engine.dispose()


def test_subscription_charge_snapshot_backfill_uses_originating_event(mig_db_url: str) -> None:
    cfg = _cfg(mig_db_url)
    command.upgrade(cfg, "48c724fa9db6")
    engine = create_engine(mig_db_url, future=True)
    owner_id = uuid.uuid4()
    subscriber_id = uuid.uuid4()
    publication_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    subscription_id = uuid.uuid4()

    try:
        with engine.begin() as connection:
            for user_id, sub, email, name in (
                (owner_id, "snapshot-owner", "owner@example.com", "Owner"),
                (subscriber_id, "snapshot-subscriber", "subscriber@example.com", "Subscriber"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO users (id, cognito_sub, email, display_name, is_admin) "
                        "VALUES (:id, :sub, :email, :name, false)"
                    ),
                    {"id": user_id, "sub": sub, "email": email, "name": name},
                )
            connection.execute(
                text(
                    "INSERT INTO publications (id, owner_user_id, handle, name, is_active) "
                    "VALUES (:id, :owner_id, 'snapshot-publication', 'Snapshot Publication', true)"
                ),
                {"id": publication_id, "owner_id": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO subscription_plans "
                    "(id, publication_id, name, monthly_price_cents, currency, "
                    "allow_open_amount, is_active) "
                    "VALUES (:id, :publication_id, 'Current tier', 2000, 'EUR', false, true)"
                ),
                {"id": plan_id, "publication_id": publication_id},
            )
            connection.execute(
                text(
                    "INSERT INTO subscriptions "
                    "(id, subscriber_user_id, publication_id, plan_id, amount_cents, status) "
                    "VALUES (:id, :subscriber_id, :publication_id, :plan_id, 2000, 'active')"
                ),
                {
                    "id": subscription_id,
                    "subscriber_id": subscriber_id,
                    "publication_id": publication_id,
                    "plan_id": plan_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO outbox_events "
                    "(id, aggregate_type, aggregate_id, event_type, event_version, payload, "
                    "status, publish_attempts) "
                    "VALUES (:id, 'subscription', :subscription_id, 'subscription.created', 1, "
                    "CAST(:payload AS jsonb), 'pending', 0)"
                ),
                {
                    "id": uuid.uuid4(),
                    "subscription_id": subscription_id,
                    "payload": json.dumps(
                        {"payload": {"amount_cents": 500, "currency": "USD"}}
                    ),
                },
            )

        command.upgrade(cfg, "head")
        with engine.connect() as connection:
            charged_amount, charged_currency = connection.execute(
                text(
                    "SELECT charged_amount_cents, charged_currency "
                    "FROM subscriptions WHERE id = :id"
                ),
                {"id": subscription_id},
            ).one()
        assert (charged_amount, charged_currency) == (500, "USD")
    finally:
        engine.dispose()
