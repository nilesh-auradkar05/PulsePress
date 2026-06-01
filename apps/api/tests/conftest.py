"""Shared pytest fixtures.

DB-backed tests require Postgres (the schema uses partial-unique indexes and
CHECK constraints that SQLite cannot express). Point ``TEST_DATABASE_URL`` at a
disposable database; tests that need it skip cleanly when it is unset.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (register all models on Base.metadata)
from app.db.base import Base

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    eng = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db(engine: Engine):
    """A session wrapped in an outer transaction that is rolled back per test."""
    conn = engine.connect()
    txn = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        txn.rollback()
        conn.close()
