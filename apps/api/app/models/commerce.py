"""Commerce context (money-shaped). All money is integer cents."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SUBSCRIPTION_STATUSES = ("active", "canceled", "expired")
GIFT_STATUSES = ("pending", "processed", "failed")
LEDGER_SOURCE_TYPES = ("subscription", "gift")
LEDGER_ACCOUNTS = ("author", "platform", "tax")


class SubscriptionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscription_plans"

    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    monthly_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    allow_open_amount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    benefits: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index(
            "uq_active_subscriber_publication",
            "subscriber_user_id",
            "publication_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint(f"status IN {SUBSCRIPTION_STATUSES}", name="status_valid"),
    )

    subscriber_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_plans.id"), index=True, nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    period_start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    period_end: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    access_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class GiftTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gift_transactions"
    __table_args__ = (
        CheckConstraint(f"status IN {GIFT_STATUSES}", name="status_valid"),
        CheckConstraint("amount_cents >= 50", name="amount_min"),
    )

    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")


class LedgerTransaction(UUIDPrimaryKeyMixin, Base):
    """Immutable. One balanced transaction per paid subscription/gift; owns the CHECKs."""

    __tablename__ = "ledger_transactions"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="source_unique"),
        CheckConstraint(f"source_type IN {LEDGER_SOURCE_TYPES}", name="source_type_valid"),
        CheckConstraint(
            "author_net_cents + platform_fee_cents + tax_cents = total_charged_cents",
            name="balanced_total",
        ),
        CheckConstraint(
            "principal_amount_cents + tax_cents = total_charged_cents",
            name="principal_plus_tax",
        ),
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
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
    """Immutable. Exactly three rows (author, platform, tax) per ledger transaction."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("ledger_transaction_id", "account", name="transaction_account_unique"),
        CheckConstraint(f"account IN {LEDGER_ACCOUNTS}", name="account_valid"),
        CheckConstraint("direction IN ('credit')", name="direction_valid"),
    )

    ledger_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id"), index=True, nullable=False
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    account: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="credit")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
