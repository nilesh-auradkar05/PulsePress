"""Read models (worker-populated)."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class PublicationDailyStats(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "publication_daily_stats"
    __table_args__ = (
        UniqueConstraint("publication_id", "stat_date", name="publication_date_unique"),
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    stat_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gift_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gross_revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    author_net_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    platform_fees_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_collected_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class UserFeedEvent(UUIDPrimaryKeyMixin, Base):
    """Durable per-reader feed rows created by worker fanout."""

    __tablename__ = "user_feed_events"
    __table_args__ = (
        Index("ix_user_feed_events_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    source_event_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationEvent(UUIDPrimaryKeyMixin, Base):
    """Backs the writer/admin publication dashboard and public-safe activity stream."""

    __tablename__ = "notification_events"

    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
