"""All 17 Phase-1 models, plus immutability registration.

Importing this package registers every model on ``Base.metadata`` (so Alembic
autogenerate and ``create_all`` see them) and wires the application-level
immutability guard on the append-only tables.
"""

from __future__ import annotations

from app.db.immutable import register_immutable

from .commerce import (
    GiftTransaction,
    LedgerEntry,
    LedgerTransaction,
    Subscription,
    SubscriptionPlan,
)
from .identity import User
from .kernel import EventProcessingAttempt, IdempotencyKey, OutboxEvent
from .operability import ReconciliationLog
from .publishing import NewsletterSend, Post, PostVersion, Publication
from .read_models import NotificationEvent, PublicationDailyStats, UserFeedEvent

register_immutable(LedgerTransaction, LedgerEntry, PostVersion, ReconciliationLog)

__all__ = [
    "User",
    "Publication",
    "Post",
    "PostVersion",
    "NewsletterSend",
    "SubscriptionPlan",
    "Subscription",
    "GiftTransaction",
    "LedgerTransaction",
    "LedgerEntry",
    "OutboxEvent",
    "IdempotencyKey",
    "EventProcessingAttempt",
    "PublicationDailyStats",
    "UserFeedEvent",
    "NotificationEvent",
    "ReconciliationLog",
]
