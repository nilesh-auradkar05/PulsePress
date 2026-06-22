"""Outbox poller behavior, including actual Postgres SKIP LOCKED claims."""

from __future__ import annotations

import datetime
import io
import threading
import uuid
from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from pulsepress_worker.adapters import (
    Boto3EventBridgePublisher,
    EventPublishError,
    LocalEventBridgePublisher,
    ReceiptStoreError,
    S3ReceiptStore,
)
from pulsepress_worker.events import EventEnvelope, utcnow
from pulsepress_worker.models import OutboxEvent
from pulsepress_worker.outbox import OutboxPoller


def _event() -> EventEnvelope:
    event_id = uuid.uuid4()
    return EventEnvelope(
        event_id=event_id,
        event_type="subscription.created",
        event_version=1,
        occurred_at=utcnow(),
        producer="api",
        correlation_id="test-correlation",
        causation_id=None,
        aggregate_type="subscription",
        aggregate_id=uuid.uuid4(),
        payload={},
    )


def _pending(db: Session, event: EventEnvelope) -> OutboxEvent:
    row = OutboxEvent(
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        event_version=event.event_version,
        payload=event.as_dict(),
        status="pending",
        publish_attempts=0,
    )
    db.add(row)
    db.flush()
    return row


def test_poller_marks_published_only_after_success(session_factory: Callable[[], Session]) -> None:
    event = _event()
    with session_factory() as db:
        with db.begin():
            row = _pending(db, event)
            row_id = row.id

    publisher = LocalEventBridgePublisher()
    result = OutboxPoller(session_factory=session_factory, publisher=publisher).poll_once()

    assert result.claimed == result.published == 1
    assert result.failed == 0
    assert publisher.published == [event]
    with session_factory() as db:
        row = db.get(OutboxEvent, row_id)
        assert row is not None
        assert row.status == "published"
        assert row.publish_attempts == 1
        assert row.published_at is not None


def test_poller_failure_is_retryable(session_factory: Callable[[], Session]) -> None:
    event = _event()
    with session_factory() as db:
        with db.begin():
            row = _pending(db, event)
            row_id = row.id

    class FailingPublisher:
        def publish(self, event: EventEnvelope) -> None:
            raise EventPublishError("EventBridge unavailable")

    failed_at = utcnow()
    first = OutboxPoller(
        session_factory=session_factory,
        publisher=FailingPublisher(),
        retry_base_seconds=5,
        clock=lambda: failed_at,
    ).poll_once()
    assert first == first.__class__(claimed=1, published=0, failed=1)
    with session_factory() as db:
        failed = db.get(OutboxEvent, row_id)
        assert failed is not None
        assert failed.status == "failed"
        assert failed.publish_attempts == 1
        assert "unavailable" in (failed.last_error or "")
        assert failed.next_attempt_at == failed_at + datetime.timedelta(seconds=5)

    recovered = LocalEventBridgePublisher()
    second = OutboxPoller(
        session_factory=session_factory,
        publisher=recovered,
        retry_base_seconds=5,
        clock=lambda: failed_at + datetime.timedelta(seconds=5),
    ).poll_once()
    assert second == second.__class__(claimed=1, published=1, failed=0)
    with session_factory() as db:
        row = db.get(OutboxEvent, row_id)
        assert row is not None
        assert row.status == "published"
        assert row.publish_attempts == 2


def test_poller_uses_postgres_skip_locked_to_avoid_double_claim(
    session_factory: Callable[[], Session],
) -> None:
    event = _event()
    with session_factory() as db:
        with db.begin():
            _pending(db, event)

    started = threading.Event()
    release = threading.Event()
    first_result: list[object] = []

    class BlockingPublisher:
        def __init__(self) -> None:
            self.calls = 0

        def publish(self, event: EventEnvelope) -> None:
            self.calls += 1
            started.set()
            assert release.wait(timeout=5)

    first_publisher = BlockingPublisher()
    first_poller = OutboxPoller(session_factory=session_factory, publisher=first_publisher)
    second_poller = OutboxPoller(
        session_factory=session_factory,
        publisher=LocalEventBridgePublisher(),
    )

    thread = threading.Thread(target=lambda: first_result.append(first_poller.poll_once()))
    thread.start()
    assert started.wait(timeout=5)

    # The first poller is still inside its transaction holding the row lock.
    # PostgreSQL must return immediately with no rows for the second poller.
    second_result = second_poller.poll_once()
    release.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert second_result.claimed == 0
    assert first_publisher.calls == 1
    assert len(first_result) == 1


def test_eventbridge_per_entry_failure_is_not_treated_as_success() -> None:
    class FailedEntryClient:
        def put_events(self, **kwargs: object) -> dict[str, object]:
            return {
                "FailedEntryCount": 1,
                "Entries": [{"ErrorCode": "AccessDenied", "ErrorMessage": "not allowed"}],
            }

    publisher = Boto3EventBridgePublisher(client=FailedEntryClient(), event_bus_name="pulsepress")
    with pytest.raises(EventPublishError, match="AccessDenied"):
        publisher.publish(_event())


def test_poller_waits_for_backoff_and_marks_terminal_failure_after_retry_exhaustion(
    session_factory: Callable[[], Session],
) -> None:
    event = _event()
    with session_factory() as db:
        with db.begin():
            row = _pending(db, event)
            row_id = row.id

    class FailingPublisher:
        def publish(self, event: EventEnvelope) -> None:
            raise EventPublishError("EventBridge unavailable")

    first_now = utcnow()
    first = OutboxPoller(
        session_factory=session_factory,
        publisher=FailingPublisher(),
        retry_base_seconds=30,
        max_attempts=2,
        clock=lambda: first_now,
    ).poll_once()
    assert first.failed == 1
    assert first.terminal == 0

    recovered = LocalEventBridgePublisher()
    before_retry = OutboxPoller(
        session_factory=session_factory,
        publisher=recovered,
        retry_base_seconds=30,
        max_attempts=2,
        clock=lambda: first_now + datetime.timedelta(seconds=29),
    ).poll_once()
    assert before_retry.claimed == 0
    assert recovered.published == []

    terminal = OutboxPoller(
        session_factory=session_factory,
        publisher=FailingPublisher(),
        retry_base_seconds=30,
        max_attempts=2,
        clock=lambda: first_now + datetime.timedelta(seconds=30),
    ).poll_once()
    assert terminal.failed == 1
    assert terminal.terminal == 1
    with session_factory() as db:
        row = db.get(OutboxEvent, row_id)
        assert row is not None
        assert row.status == "failed"
        assert row.next_attempt_at is None
        assert row.terminal_at is not None


def test_poller_claims_legacy_failed_rows_without_a_retry_timestamp(
    session_factory: Callable[[], Session],
) -> None:
    event = _event()
    with session_factory() as db:
        with db.begin():
            row = _pending(db, event)
            row.status = "failed"
            row.publish_attempts = 1
            row.next_attempt_at = None

    publisher = LocalEventBridgePublisher()
    result = OutboxPoller(session_factory=session_factory, publisher=publisher).poll_once()

    assert result.claimed == 1
    assert result.published == 1
    assert publisher.published == [event]


def test_poller_defers_unimplemented_event_types_without_publishing(
    session_factory: Callable[[], Session],
) -> None:
    event = EventEnvelope(
        event_id=uuid.uuid4(),
        event_type="post.published",
        event_version=1,
        occurred_at=utcnow(),
        producer="api",
        correlation_id="test-correlation",
        causation_id=None,
        aggregate_type="post",
        aggregate_id=uuid.uuid4(),
        payload={"post_id": str(uuid.uuid4())},
    )
    with session_factory() as db:
        with db.begin():
            row = _pending(db, event)
            row_id = row.id

    publisher = LocalEventBridgePublisher()
    result = OutboxPoller(session_factory=session_factory, publisher=publisher).poll_once()

    assert result.claimed == 0
    assert publisher.published == []
    with session_factory() as db:
        row = db.get(OutboxEvent, row_id)
        assert row is not None
        assert row.status == "pending"


def test_s3_receipts_use_create_only_writes_and_reject_conflicting_contents() -> None:
    class PreconditionFailed(Exception):
        response = {"Error": {"Code": "PreconditionFailed"}}

    class CreateOnlyClient:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def put_object(self, **kwargs: object) -> None:
            assert kwargs["IfNoneMatch"] == "*"
            key = str(kwargs["Key"])
            if key in self.objects:
                raise PreconditionFailed()
            body = kwargs["Body"]
            assert isinstance(body, bytes)
            self.objects[key] = body

        def get_object(self, **kwargs: object) -> dict[str, object]:
            return {"Body": io.BytesIO(self.objects[str(kwargs["Key"])])}

    client = CreateOnlyClient()
    store = S3ReceiptStore(client=client, bucket="receipts")

    assert store.put_receipt(key="receipts/gift/event.json", contents={"amount": 1000}) == (
        "receipts/gift/event.json"
    )
    assert store.put_receipt(key="receipts/gift/event.json", contents={"amount": 1000}) == (
        "receipts/gift/event.json"
    )
    with pytest.raises(ReceiptStoreError, match="immutable receipt conflict"):
        store.put_receipt(key="receipts/gift/event.json", contents={"amount": 2000})
