"""PostgreSQL fixtures for worker behavior tests."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

API_DIRECTORY = Path(__file__).resolve().parents[2] / "api"
if str(API_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(API_DIRECTORY))


def _migration_config(database_url: str) -> Config:
    config = Config(str(API_DIRECTORY / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIRECTORY / "alembic"))
    config.set_main_option("prepend_sys_path", str(API_DIRECTORY))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _worker_database_url(database_url: str) -> tuple[str, str]:
    base, database_name = database_url.rsplit("/", 1)
    return f"{base}/{database_name}_worker", f"{base}/postgres"


def _run_admin_statement(admin_url: str, statement: str) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    try:
        with engine.connect() as connection:
            connection.execute(text(statement))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set")
    worker_database_url, admin_url = _worker_database_url(database_url)
    worker_database_name = worker_database_url.rsplit("/", 1)[1]
    _run_admin_statement(admin_url, f'DROP DATABASE IF EXISTS "{worker_database_name}"')
    _run_admin_statement(admin_url, f'CREATE DATABASE "{worker_database_name}"')
    command.upgrade(_migration_config(worker_database_url), "head")
    engine = create_engine(worker_database_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()
        _run_admin_statement(admin_url, f'DROP DATABASE IF EXISTS "{worker_database_name}"')


@pytest.fixture()
def session_factory(engine: Engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def clear_tables() -> None:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE users, outbox_events, event_processing_attempts "
                "RESTART IDENTITY CASCADE"
            )

    clear_tables()
    yield factory
    clear_tables()
