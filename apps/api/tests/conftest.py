"""Shared pytest fixtures.

DB-backed tests require Postgres (the schema uses partial-unique indexes and
CHECK constraints that SQLite cannot express). Point ``TEST_DATABASE_URL`` at a
disposable database; tests that need it skip cleanly when it is unset.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (register all models on Base.metadata)
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

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


@pytest.fixture()
def client(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient in local-auth mode, sharing the test ``engine``.

    The app's request sessions commit to the same engine the ``db`` fixture
    reads, so committed commerce writes are visible to DB assertions.
    """
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "local_jwt_secret", "test-local-jwt-secret-at-least-32-bytes")
    app = create_app()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
