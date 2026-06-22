"""Transactional outbox polling and worker-originated event persistence."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .adapters import EventPublisher
from .events import EventEnvelope, utcnow
from .models import OutboxEvent

S4_ROUTABLE_EVENT_TYPES = (
    "subscription.created",
    "subscription.tier_changed",
    "subscription.canceled",
    "gift.sent",
    "ledger.transaction.recorded",
    "event.processing.failed",
)


@dataclass(frozen=True)
class PollResult:
    claimed: int
    published: int
    failed: int
    terminal: int = 0


class OutboxPoller:
    """Publish-then-mark outbox delivery with Postgres ``SKIP LOCKED`` claims."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        publisher: EventPublisher,
        batch_size: int = 25,
        retry_base_seconds: int = 5,
        max_attempts: int = 10,
        clock: Callable[[], datetime.datetime] = utcnow,
    ) -> None:
        if retry_base_seconds < 1:
            raise ValueError("retry_base_seconds must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._session_factory = session_factory
        self._publisher = publisher
        self._batch_size = batch_size
        self._retry_base_seconds = retry_base_seconds
        self._max_attempts = max_attempts
        self._clock = clock

    def poll_once(self) -> PollResult:
        published = 0
        failed = 0
        claimed = 0
        terminal = 0
        now = self._clock()
        with self._session_factory() as db:
            with db.begin():
                statement = (
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.event_type.in_(S4_ROUTABLE_EVENT_TYPES),
                        or_(
                            OutboxEvent.status == "pending",
                            and_(
                                OutboxEvent.status == "failed",
                                OutboxEvent.terminal_at.is_(None),
                                or_(
                                    OutboxEvent.next_attempt_at.is_(None),
                                    OutboxEvent.next_attempt_at <= now,
                                ),
                            ),
                        )
                    )
                    .order_by(OutboxEvent.created_at, OutboxEvent.id)
                    .limit(self._batch_size)
                    .with_for_update(skip_locked=True)
                )
                events = list(db.execute(statement).scalars())
                claimed = len(events)
                for event in events:
                    event.publish_attempts += 1
                    try:
                        envelope = EventEnvelope.from_mapping(event.payload)
                        self._publisher.publish(envelope)
                    except Exception as exc:
                        event.last_error = str(exc)[:2048]
                        if event.publish_attempts >= self._max_attempts:
                            event.status = "failed"
                            event.next_attempt_at = None
                            event.terminal_at = now
                            terminal += 1
                        else:
                            event.status = "failed"
                            event.next_attempt_at = now + datetime.timedelta(
                                seconds=self._retry_delay_seconds(event.publish_attempts)
                            )
                        failed += 1
                    else:
                        event.status = "published"
                        event.published_at = utcnow()
                        event.last_error = None
                        event.next_attempt_at = None
                        published += 1
        return PollResult(
            claimed=claimed,
            published=published,
            failed=failed,
            terminal=terminal,
        )

    def _retry_delay_seconds(self, attempt_number: int) -> int:
        return self._retry_base_seconds * (2 ** (attempt_number - 1))


def enqueue_worker_event(db: Session, event: EventEnvelope) -> OutboxEvent:
    """Write one worker-originated domain event in the current DB transaction."""
    outbox_event = OutboxEvent(
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        event_version=event.event_version,
        payload=event.as_dict(),
        status="pending",
        publish_attempts=0,
    )
    db.add(outbox_event)
    db.flush()
    return outbox_event
