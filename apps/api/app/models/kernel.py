"""Reliability kernel (shared): outbox, idempotency, worker attempts."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

OUTBOX_STATUSES = ("pending", "published", "failed", "superseded", "discarded")
ATTEMPT_STATUSES = ("started", "succeeded", "failed")


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(f"status IN {OUTBOX_STATUSES}", name="status_valid"),
    )

    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False, default="pending")
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    published_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    terminal_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="user_key_unique"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict | None] = mapped_column(JSONB)
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class EventProcessingAttempt(UUIDPrimaryKeyMixin, Base):
    """Worker idempotency ledger (logical link to outbox; no hard FK across the async boundary)."""

    __tablename__ = "event_processing_attempts"
    __table_args__ = (
        CheckConstraint(f"status IN {ATTEMPT_STATUSES}", name="status_valid"),
        UniqueConstraint("event_id", name="event_unique"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    # A crashed worker leaves its row in ``started``. A later SQS delivery may
    # reclaim the event after this lease expires without duplicating durable work.
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    failure_event_emitted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
