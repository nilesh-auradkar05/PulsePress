"""Transactional-outbox writer (SPEC §5.3, CLAUDE.md §7).

Commerce writes and ``publishPost`` append an ``outbox_events`` row in the *same*
transaction as the business write, eliminating the dual-write problem. The row's
``payload`` carries the full event envelope (``event_catalog.md`` §1) — including
``correlation_id`` — because the table has no dedicated envelope columns; the
Sprint-4 poller reads the envelope straight from ``payload``.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session

from app.models import OutboxEvent


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def enqueue_event(
    db: Session,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict,
    correlation_id: str,
    event_version: int = 1,
    causation_id: str | None = None,
) -> OutboxEvent:
    """Append one pending ``outbox_events`` row wrapping the standard envelope."""
    envelope = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": event_version,
        "occurred_at": _utcnow().isoformat(),
        "producer": "api",
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "aggregate_type": aggregate_type,
        "aggregate_id": str(aggregate_id),
        "payload": payload,
    }
    event = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        event_version=event_version,
        payload=envelope,
        status="pending",
        publish_attempts=0,
    )
    db.add(event)
    db.flush()
    return event
