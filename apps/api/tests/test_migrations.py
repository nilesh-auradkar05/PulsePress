"""Migration roundtrip test (S2-T01) — alembic upgrade head then downgrade base.

Runs against a disposable sibling database derived from ``TEST_DATABASE_URL`` so
it does not disturb the metadata-built schema used by the other DB tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

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
