"""Worker-owned SQLAlchemy mappings for the shared API database.

The worker intentionally maps only tables it reads or writes. Alembic remains
owned by ``apps/api``; keeping these mappings local lets the worker ship as an
independent container without importing FastAPI application code.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class User(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "users"

    cognito_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(nullable=False, default=False)


class Publication(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "publications"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    handle: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class Subscription(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "subscriptions"

    subscriber_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publications.id"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    charged_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    charged_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class SubscriptionPlan(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "subscription_plans"

    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publications.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    monthly_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    allow_open_amount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class GiftTransaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "gift_transactions"

    sender_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publications.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "outbox_events"

    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class EventProcessingAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "event_processing_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('started', 'succeeded', 'failed')", name="status_valid"),
        UniqueConstraint("event_id", name="event_unique"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    failure_event_emitted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class LedgerTransaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ledger_transactions"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="source_unique"),
        CheckConstraint("source_type IN ('subscription', 'gift')", name="source_type_valid"),
        CheckConstraint(
            "author_net_cents + platform_fee_cents + tax_cents = total_charged_cents",
            name="balanced_total",
        ),
        CheckConstraint(
            "principal_amount_cents + tax_cents = total_charged_cents",
            name="principal_plus_tax",
        ),
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publications.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    source_event_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    principal_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_net_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    platform_fee_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_charged_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LedgerEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("ledger_transaction_id", "account", name="transaction_account_unique"),
        CheckConstraint("account IN ('author', 'platform', 'tax')", name="account_valid"),
        CheckConstraint("direction IN ('credit')", name="direction_valid"),
    )

    ledger_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id"), nullable=False
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publications.id"), nullable=False)
    account: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="credit")


class PublicationDailyStats(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "publication_daily_stats"
    __table_args__ = (
        UniqueConstraint("publication_id", "stat_date", name="publication_date_unique"),
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publications.id"), nullable=False)
    stat_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gift_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gross_revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    author_net_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    platform_fees_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_collected_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
