"""Worker database engine and session factory."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_session_factory(database_url: str) -> Callable[[], Session]:
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
