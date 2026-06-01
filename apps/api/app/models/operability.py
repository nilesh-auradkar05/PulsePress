"""Operability context: append-only reconciliation log."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

RECONCILIATION_ACTIONS = ("retry", "amend", "discard", "manual_fix")


class ReconciliationLog(UUIDPrimaryKeyMixin, Base):
    """Immutable. Every human override on permanent record."""

    __tablename__ = "reconciliation_log"
    __table_args__ = (
        CheckConstraint(f"action IN {RECONCILIATION_ACTIONS}", name="action_valid"),
        CheckConstraint("char_length(reason) >= 10", name="reason_min_length"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    state_before: Mapped[dict | None] = mapped_column(JSONB)
    state_after: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
