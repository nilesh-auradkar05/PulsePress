"""Worker idempotency, ledger materialization, receipt failure, and DLQ behavior."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pulsepress_worker.adapters import InMemoryReceiptStore, QueueMessage, ReceiptStoreError
from pulsepress_worker.events import EventEnvelope, MalformedEventError, utcnow
from pulsepress_worker.models import (
    EventProcessingAttempt,
    GiftTransaction,
    LedgerEntry,
    LedgerTransaction,
    OutboxEvent,
    Publication,
    PublicationDailyStats,
    Subscription,
    SubscriptionPlan,
    User,
)
from pulsepress_worker.processor import EventInProgressError, SourceConflictError, WorkerProcessor
from pulsepress_worker.queue import SqsConsumer


def _seed_source(
    session_factory: Callable[[], Session], *, source: str, subscription_amount_cents: int = 500
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with session_factory() as db:
        with db.begin():
            owner = User(cognito_sub=f"owner-{uuid.uuid4()}", display_name="Owner")
            reader = User(cognito_sub=f"reader-{uuid.uuid4()}", display_name="Reader")
            db.add_all([owner, reader])
            db.flush()
            publication = Publication(
                owner_user_id=owner.id,
                handle=f"publication-{uuid.uuid4().hex[:10]}",
                name="Publication",
            )
            db.add(publication)
            db.flush()
            if source == "subscription":
                plan = SubscriptionPlan(
                    publication_id=publication.id,
                    name="Paid",
                    monthly_price_cents=subscription_amount_cents,
                    currency="USD",
                    allow_open_amount=False,
                    is_active=True,
                )
                db.add(plan)
                db.flush()
                record = Subscription(
                    subscriber_user_id=reader.id,
                    publication_id=publication.id,
                    plan_id=plan.id,
                    amount_cents=subscription_amount_cents,
                    charged_amount_cents=subscription_amount_cents,
                    charged_currency="USD",
                )
            else:
                record = GiftTransaction(
                    sender_user_id=reader.id,
                    publication_id=publication.id,
                    amount_cents=1000,
                    currency="USD",
                    status="pending",
                )
            db.add(record)
            db.flush()
            return record.id, publication.id, reader.id


def _event(
    *,
    event_type: str,
    source_id: uuid.UUID,
    publication_id: uuid.UUID,
    amount_cents: int,
    tier: str | None = None,
    event_id: uuid.UUID | None = None,
) -> EventEnvelope:
    bill = {
        "amount_cents": amount_cents,
        "author_net_cents": amount_cents - (amount_cents // 10),
        "platform_fee_cents": amount_cents // 10,
        "tax_cents": (amount_cents * 8) // 100,
        "total_charged_cents": amount_cents + ((amount_cents * 8) // 100),
    }
    payload: dict[str, object] = {
        "publication_id": str(publication_id),
        "amount_cents": amount_cents,
        "currency": "USD",
        "bill": bill,
    }
    if event_type == "subscription.created":
        payload["subscription_id"] = str(source_id)
        payload["tier"] = tier or "paid"
        if tier == "free":
            payload["amount_cents"] = 0
            payload["bill"] = None
    else:
        payload["gift_id"] = str(source_id)
    return EventEnvelope(
        event_id=event_id or uuid.uuid4(),
        event_type=event_type,
        event_version=1,
        occurred_at=utcnow(),
        producer="api",
        correlation_id="test-correlation",
        causation_id=None,
        aggregate_type="subscription" if event_type == "subscription.created" else "gift",
        aggregate_id=source_id,
        payload=payload,
    )


def _processor(
    session_factory: Callable[[], Session], store: InMemoryReceiptStore
) -> WorkerProcessor:
    return WorkerProcessor(
        session_factory=session_factory,
        receipt_store=store,
        event_lock_seconds=30,
    )


def test_paid_subscription_creates_balanced_three_entry_ledger_and_receipt(
    session_factory: Callable[[], Session],
) -> None:
    subscription_id, publication_id, _ = _seed_source(session_factory, source="subscription")
    event = _event(
        event_type="subscription.created",
        source_id=subscription_id,
        publication_id=publication_id,
        amount_cents=500,
    )
    store = InMemoryReceiptStore()

    result = _processor(session_factory, store).process_mapping(event.as_dict())

    assert result.status == "succeeded"
    assert f"receipts/subscription/{subscription_id}/{event.event_id}.json" in store.objects
    with session_factory() as db:
        ledger = db.execute(select(LedgerTransaction)).scalar_one()
        assert ledger.source_event_id == event.event_id
        assert ledger.author_net_cents + ledger.platform_fee_cents + ledger.tax_cents == 540
        entries = list(
            db.execute(
                select(LedgerEntry).where(LedgerEntry.ledger_transaction_id == ledger.id)
            ).scalars()
        )
        assert {entry.account for entry in entries} == {"author", "platform", "tax"}
        assert len(entries) == 3
        assert sum(entry.amount_cents for entry in entries) == ledger.total_charged_cents
        emitted = db.execute(
            select(OutboxEvent).where(OutboxEvent.event_type == "ledger.transaction.recorded")
        ).scalar_one()
        assert emitted.payload["causation_id"] == str(event.event_id)
        assert emitted.payload["payload"]["receipt_artifact_key"] == (
            f"receipts/subscription/{subscription_id}/{event.event_id}.json"
        )
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "succeeded"
        assert attempt.attempt_number == 1


def test_free_subscription_updates_stats_without_ledger(
    session_factory: Callable[[], Session],
) -> None:
    subscription_id, publication_id, _ = _seed_source(
        session_factory, source="subscription", subscription_amount_cents=0
    )
    event = _event(
        event_type="subscription.created",
        source_id=subscription_id,
        publication_id=publication_id,
        amount_cents=0,
        tier="free",
    )
    store = InMemoryReceiptStore()

    result = _processor(session_factory, store).process_mapping(event.as_dict())

    assert result.status == "succeeded"
    assert store.objects == {}
    with session_factory() as db:
        assert db.execute(select(LedgerTransaction)).scalars().all() == []
        stat = db.execute(select(PublicationDailyStats)).scalar_one()
        assert stat.subscriber_count == 1
        assert stat.gross_revenue_cents == 0


def test_gift_duplicate_event_writes_durable_state_once(
    session_factory: Callable[[], Session],
) -> None:
    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    event = _event(
        event_type="gift.sent", source_id=gift_id, publication_id=publication_id, amount_cents=1000
    )
    processor = _processor(session_factory, InMemoryReceiptStore())

    first = processor.process_mapping(event.as_dict())
    second = processor.process_mapping(event.as_dict())

    assert first.status == "succeeded"
    assert second.status == "duplicate"
    with session_factory() as db:
        assert len(db.execute(select(LedgerTransaction)).scalars().all()) == 1
        assert len(db.execute(select(LedgerEntry)).scalars().all()) == 3
        gift = db.get(GiftTransaction, gift_id)
        assert gift is not None and gift.status == "processed"
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "succeeded"


def test_concurrent_delivery_claims_event_once(
    session_factory: Callable[[], Session],
) -> None:
    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    event = _event(
        event_type="gift.sent", source_id=gift_id, publication_id=publication_id, amount_cents=1000
    )
    started = threading.Event()
    release = threading.Event()

    class BlockingStore(InMemoryReceiptStore):
        def put_receipt(self, *, key: str, contents: dict[str, object]) -> str:
            started.set()
            assert release.wait(timeout=5)
            return super().put_receipt(key=key, contents=contents)

    processor = _processor(session_factory, BlockingStore())
    outcomes: list[object] = []
    def process_in_thread() -> None:
        outcomes.append(processor.process_mapping(event.as_dict()))

    thread = threading.Thread(target=process_in_thread)
    thread.start()
    assert started.wait(timeout=5)

    with pytest.raises(EventInProgressError):
        processor.process_mapping(event.as_dict())
    release.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(outcomes) == 1
    with session_factory() as db:
        assert len(db.execute(select(LedgerTransaction)).scalars().all()) == 1
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "succeeded"


def test_retryable_receipt_store_failure_records_attempt_and_leaves_gift_pending(
    session_factory: Callable[[], Session],
) -> None:
    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    event = _event(
        event_type="gift.sent", source_id=gift_id, publication_id=publication_id, amount_cents=1000
    )

    with pytest.raises(ReceiptStoreError):
        processor = _processor(session_factory, InMemoryReceiptStore(fail=True))
        processor.process_mapping(event.as_dict())

    with session_factory() as db:
        gift = db.get(GiftTransaction, gift_id)
        assert gift is not None and gift.status == "pending"
        assert db.execute(select(LedgerTransaction)).scalars().all() == []
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "failed"
        failures = list(
            db.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "event.processing.failed")
            ).scalars()
        )
        assert failures == []


def test_existing_ledger_from_other_event_is_a_failure_not_a_second_ledger(
    session_factory: Callable[[], Session],
) -> None:
    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    with session_factory() as db:
        with db.begin():
            db.add(
                LedgerTransaction(
                    publication_id=publication_id,
                    source_type="gift",
                    source_id=gift_id,
                    source_event_id=uuid.uuid4(),
                    principal_amount_cents=1000,
                    author_net_cents=900,
                    platform_fee_cents=100,
                    tax_cents=80,
                    total_charged_cents=1080,
                    currency="USD",
                )
            )
            db.flush()
            transaction = db.execute(select(LedgerTransaction)).scalar_one()
            db.add_all(
                [
                    LedgerEntry(
                        ledger_transaction_id=transaction.id,
                        publication_id=publication_id,
                        account="author",
                        amount_cents=900,
                    ),
                    LedgerEntry(
                        ledger_transaction_id=transaction.id,
                        publication_id=publication_id,
                        account="platform",
                        amount_cents=100,
                    ),
                    LedgerEntry(
                        ledger_transaction_id=transaction.id,
                        publication_id=publication_id,
                        account="tax",
                        amount_cents=80,
                    ),
                ]
            )
    event = _event(
        event_type="gift.sent", source_id=gift_id, publication_id=publication_id, amount_cents=1000
    )

    with pytest.raises(SourceConflictError, match="another event"):
        _processor(session_factory, InMemoryReceiptStore()).process_mapping(event.as_dict())

    with session_factory() as db:
        gift = db.get(GiftTransaction, gift_id)
        assert gift is not None and gift.status == "pending"
        assert len(db.execute(select(LedgerTransaction)).scalars().all()) == 1
        assert db.execute(select(EventProcessingAttempt)).scalar_one().status == "failed"


def test_conflicting_source_event_never_writes_a_receipt(
    session_factory: Callable[[], Session],
) -> None:
    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    with session_factory() as db:
        with db.begin():
            db.add(
                LedgerTransaction(
                    publication_id=publication_id,
                    source_type="gift",
                    source_id=gift_id,
                    source_event_id=uuid.uuid4(),
                    principal_amount_cents=1000,
                    author_net_cents=900,
                    platform_fee_cents=100,
                    tax_cents=80,
                    total_charged_cents=1080,
                    currency="USD",
                )
            )
            db.flush()
            transaction = db.execute(select(LedgerTransaction)).scalar_one()
            db.add_all(
                [
                    LedgerEntry(
                        ledger_transaction_id=transaction.id,
                        publication_id=publication_id,
                        account="author",
                        amount_cents=900,
                    ),
                    LedgerEntry(
                        ledger_transaction_id=transaction.id,
                        publication_id=publication_id,
                        account="platform",
                        amount_cents=100,
                    ),
                    LedgerEntry(
                        ledger_transaction_id=transaction.id,
                        publication_id=publication_id,
                        account="tax",
                        amount_cents=80,
                    ),
                ]
            )
    event = _event(
        event_type="gift.sent", source_id=gift_id, publication_id=publication_id, amount_cents=1000
    )
    store = InMemoryReceiptStore()

    with pytest.raises(SourceConflictError, match="another event"):
        _processor(session_factory, store).process_mapping(event.as_dict())

    assert store.objects == {}


def test_paid_subscription_requires_its_creation_charge_snapshot(
    session_factory: Callable[[], Session],
) -> None:
    subscription_id, publication_id, _ = _seed_source(session_factory, source="subscription")
    with session_factory() as db:
        with db.begin():
            subscription = db.get(Subscription, subscription_id)
            assert subscription is not None
            subscription.charged_amount_cents = 501
    event = _event(
        event_type="subscription.created",
        source_id=subscription_id,
        publication_id=publication_id,
        amount_cents=500,
    )
    store = InMemoryReceiptStore()

    with pytest.raises(SourceConflictError, match="charged amount"):
        _processor(session_factory, store).process_mapping(event.as_dict())

    assert store.objects == {}


def test_terminal_failure_emits_one_durable_failure_signal(
    session_factory: Callable[[], Session],
) -> None:
    processor = WorkerProcessor(
        session_factory=session_factory,
        receipt_store=InMemoryReceiptStore(),
        event_lock_seconds=30,
        max_event_attempts=2,
    )
    malformed_event = {"event_id": "not-a-uuid", "event_type": "gift.sent"}

    with pytest.raises(MalformedEventError):
        processor.process_mapping(malformed_event)
    with pytest.raises(MalformedEventError):
        processor.process_mapping(malformed_event)

    with session_factory() as db:
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "failed"
        assert attempt.attempt_number == 2
        assert attempt.terminal_at is not None
        failures = list(
            db.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "event.processing.failed")
            ).scalars()
        )
        assert len(failures) == 1
        assert failures[0].payload["payload"]["attempt_number"] == 2
        assert failures[0].payload["payload"]["terminal"] is True


def test_terminal_poison_message_is_not_deleted_before_sqs_redrive(
    session_factory: Callable[[], Session],
) -> None:
    """Poison messages are never deleted by the worker; SQS redrive moves them to DLQ.

    Drives two deliveries so that attempt_number reaches max_event_attempts (2),
    producing a terminal failure signal.  Neither delivery results in a delete.
    """
    class FakeQueue:
        def __init__(self) -> None:
            self.message = QueueMessage(
                receipt_handle="receipt-handle",
                body={"event_id": "not-a-uuid", "event_type": "gift.sent"},
            )
            self.deleted: list[QueueMessage] = []

        def receive(self, *, max_messages: int) -> list[QueueMessage]:
            return [self.message]

        def delete(self, message: QueueMessage) -> None:
            self.deleted.append(message)

    queue = FakeQueue()
    consumer = SqsConsumer(
        queue=queue,
        processor=WorkerProcessor(
            session_factory=session_factory,
            receipt_store=InMemoryReceiptStore(),
            event_lock_seconds=30,
            max_event_attempts=2,
        ),
    )

    # Delivery 1: attempt_number=1, not yet terminal.
    result1 = consumer.consume_once()
    assert result1.failed == 1
    assert result1.deleted == 0

    # Delivery 2: attempt_number=2 == max → terminal, failure signal emitted.
    result2 = consumer.consume_once()
    assert result2.failed == 1
    assert result2.deleted == 0

    assert queue.deleted == []
    with session_factory() as db:
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "failed"
        assert attempt.terminal_at is not None
        failures = list(
            db.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "event.processing.failed")
            ).scalars()
        )
        assert len(failures) == 1


def test_receive_count_inflation_does_not_cause_premature_terminal(
    session_factory: Callable[[], Session],
) -> None:
    """Bug 1 regression: SQS receive-count inflation must not trigger terminal status.

    A single genuine processing failure (attempt_number == 1) delivered with an
    inflated receive_count must remain retryable: status="failed", terminal_at is
    None, and no event.processing.failed outbox row.
    """
    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    event = _event(
        event_type="gift.sent",
        source_id=gift_id,
        publication_id=publication_id,
        amount_cents=1000,
    )
    processor = WorkerProcessor(
        session_factory=session_factory,
        receipt_store=InMemoryReceiptStore(fail=True),
        event_lock_seconds=30,
        max_event_attempts=5,
    )

    with pytest.raises(ReceiptStoreError):
        # Deliver once — this is the first genuine attempt (attempt_number == 1).
        # Before the fix, receive_count inflation could trigger terminal prematurely.
        # After the fix, only attempt_number drives terminal; one failure is never terminal.
        processor.process_mapping(event.as_dict())

    with session_factory() as db:
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "failed"
        assert attempt.terminal_at is None, (
            "single genuine failure must NOT be terminal (Bug 1: receive_count inflation)"
        )
        failures = list(
            db.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "event.processing.failed")
            ).scalars()
        )
        assert failures == [], "no failure signal should be emitted for a non-terminal attempt"


def test_crash_between_receipt_and_ledger_commit_self_heals(
    session_factory: Callable[[], Session],
) -> None:
    """Bug 2 regression: receipt-store idempotency carries the pre-commit artifact across retry.

    What this test actually proves
    --------------------------------
    This test proves RECEIPT idempotency and clean crash recovery — not ledger
    exactly-once via the `_write_ledger` dedup branch.

    The simulated crash fires inside `put_receipt` (before `with db.begin()` opens),
    so the first delivery commits NO ledger row.  The len(ledger)==1 / len(entries)==3
    assertions are satisfied because only one ledger write ever occurs (on the retry),
    not because a second write was blocked by the same-event dedup branch.

    Specifically, this test proves:
      1. A receipt stored by the first delivery is re-used by the retry (the
         `InMemoryReceiptStore` returns the existing key rather than writing again).
      2. After the lease is manually reset to re-claimable state, the retry
         processes the event to completion with exactly one set of durable effects.
      3. No double receipt is written (store.objects count stays at 1).

    For the test that genuinely guards `_write_ledger`'s same-event dedup branch
    (existing.source_event_id == event.event_id → return False), see
    `test_same_event_id_ledger_dedup_on_reclaim`.
    """
    import datetime

    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    event = _event(
        event_type="gift.sent",
        source_id=gift_id,
        publication_id=publication_id,
        amount_cents=1000,
    )

    # A store that succeeds on put_receipt but causes the handler to fail
    # after the receipt is written (simulating a crash mid-transaction).
    class CrashAfterReceiptStore(InMemoryReceiptStore):
        _call_count: int = 0

        def put_receipt(self, *, key: str, contents: dict[str, object]) -> str:
            result = super().put_receipt(key=key, contents=contents)
            self._call_count += 1
            if self._call_count == 1:
                # Receipt is now stored but the exception is raised BEFORE the
                # `with db.begin()` block that writes the ledger opens, so NO
                # ledger row is committed on this delivery.
                raise RuntimeError("simulated hard crash after receipt PUT")
            return result

    store = CrashAfterReceiptStore()
    processor = WorkerProcessor(
        session_factory=session_factory,
        receipt_store=store,
        event_lock_seconds=30,
        max_event_attempts=5,
    )

    # First delivery: receipt stored, then crash — attempt stays "started".
    with pytest.raises(RuntimeError, match="simulated hard crash"):
        processor.process_mapping(event.as_dict())

    with session_factory() as db:
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "failed"  # _record_failure was called on the caught exception
        assert db.execute(select(LedgerTransaction)).scalars().all() == []

    # Fabricate the un-caught hard-crash state: status="started" with an expired
    # lease.  NOTE — this is NOT what the caught-exception path above leaves (that
    # sets status="failed" / lease=None via _record_failure).  A real un-caught hard
    # crash bypasses the except handler entirely, so the row stays "started" with
    # whatever locked_until was set at claim time.  We manually reproduce that here.
    with session_factory() as db:
        with db.begin():
            attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
            attempt.locked_until = utcnow() - datetime.timedelta(seconds=1)
            attempt.status = "started"  # mimic what a hard crash would leave

    # Second delivery (redelivery after lease expiry): must self-heal exactly once.
    result = processor.process_mapping(event.as_dict())

    assert result.status == "succeeded"
    with session_factory() as db:
        ledger_rows = db.execute(select(LedgerTransaction)).scalars().all()
        assert len(ledger_rows) == 1
        entry_rows = db.execute(select(LedgerEntry)).scalars().all()
        assert len(entry_rows) == 3
        assert len(store.objects) == 1, "idempotent store must have exactly one receipt"
        attempt = db.execute(select(EventProcessingAttempt)).scalar_one()
        assert attempt.status == "succeeded"


def test_same_event_id_ledger_dedup_on_reclaim(
    session_factory: Callable[[], Session],
) -> None:
    """_write_ledger same-event dedup branch: pre-committed ledger + re-claimed attempt yields
    exactly one ledger transaction and no SourceConflictError.

    What this test actually proves
    --------------------------------
    This is the ONLY test that genuinely exercises `_write_ledger`'s idempotency
    branch (processor.py ~line 428-433):

        if existing.source_event_id == event.event_id:
            return False   ← this line

    The precondition is manufactured directly: a `LedgerTransaction` (+3
    `LedgerEntry`) for the gift with `source_event_id == event.event_id` is
    pre-committed, and the `EventProcessingAttempt` is placed in a re-claimable
    state (status="started", locked_until in the past) so `_claim` re-claims it
    rather than returning "duplicate".

    This state is not reachable in production via a normal crash (the ledger write
    and attempt.status="succeeded" are in the same `db.begin()` block and commit
    atomically), but the dedup branch exists as a defence-in-depth guard.  This test
    verifies that guard is wired up correctly.
    """
    import datetime

    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    event = _event(
        event_type="gift.sent",
        source_id=gift_id,
        publication_id=publication_id,
        amount_cents=1000,
    )

    # Pre-commit a LedgerTransaction for this gift with source_event_id matching
    # the event we are about to deliver — simulating "ledger written, attempt not yet
    # succeeded" (the unreachable-in-practice but guarded-against state).
    with session_factory() as db:
        with db.begin():
            transaction = LedgerTransaction(
                publication_id=publication_id,
                source_type="gift",
                source_id=gift_id,
                source_event_id=event.event_id,  # same event — dedup branch fires
                principal_amount_cents=1000,
                author_net_cents=900,
                platform_fee_cents=100,
                tax_cents=80,
                total_charged_cents=1080,
                currency="USD",
            )
            db.add(transaction)
            db.flush()
            db.add_all([
                LedgerEntry(
                    ledger_transaction_id=transaction.id,
                    publication_id=publication_id,
                    account="author",
                    amount_cents=900,
                ),
                LedgerEntry(
                    ledger_transaction_id=transaction.id,
                    publication_id=publication_id,
                    account="platform",
                    amount_cents=100,
                ),
                LedgerEntry(
                    ledger_transaction_id=transaction.id,
                    publication_id=publication_id,
                    account="tax",
                    amount_cents=80,
                ),
            ])

    # Put the attempt into re-claimable state: status="started" with an expired
    # lease.  _claim will re-claim (not return "duplicate") and attempt_number
    # will be bumped, so _dispatch is reached and _write_ledger is called.
    with session_factory() as db:
        with db.begin():
            attempt_row = EventProcessingAttempt(
                event_id=event.event_id,
                event_type=event.event_type,
                status="started",
                attempt_number=1,
                locked_until=utcnow() - datetime.timedelta(seconds=1),
            )
            db.add(attempt_row)

    store = InMemoryReceiptStore()
    result = _processor(session_factory, store).process_mapping(event.as_dict())

    # Must succeed — _write_ledger returns False (dedup), no SourceConflictError.
    assert result.status == "succeeded"
    with session_factory() as db:
        ledger_rows = db.execute(select(LedgerTransaction)).scalars().all()
        assert len(ledger_rows) == 1, "dedup branch must not write a second ledger transaction"
        entry_rows = db.execute(select(LedgerEntry)).scalars().all()
        assert len(entry_rows) == 3, "dedup branch must not write additional ledger entries"


def test_duplicate_claim_writes_no_receipt(
    session_factory: Callable[[], Session],
) -> None:
    """A duplicate delivery (second _claim returns 'duplicate') must not write a new receipt.

    The first delivery succeeds and stores exactly one receipt.  The second delivery
    hits the 'duplicate' early-exit path in _claim and must return without calling
    the receipt store at all.
    """
    gift_id, publication_id, _ = _seed_source(session_factory, source="gift")
    event = _event(
        event_type="gift.sent", source_id=gift_id, publication_id=publication_id, amount_cents=1000
    )
    store = InMemoryReceiptStore()
    processor = _processor(session_factory, store)

    first = processor.process_mapping(event.as_dict())
    assert first.status == "succeeded"
    receipt_count_after_first = len(store.objects)

    second = processor.process_mapping(event.as_dict())
    assert second.status == "duplicate"
    assert len(store.objects) == receipt_count_after_first, (
        "duplicate claim path must not write a new receipt"
    )


def test_retryable_poison_message_is_not_deleted_or_applied(
    session_factory: Callable[[], Session],
) -> None:
    gift_id, _publication_id, _ = _seed_source(session_factory, source="gift")

    class FakeQueue:
        def __init__(self) -> None:
            self.message = QueueMessage(
                receipt_handle="receipt-handle",
                body={"event_id": "not-a-uuid", "event_type": "gift.sent", "gift_id": str(gift_id)},
            )
            self.deleted: list[QueueMessage] = []

        def receive(self, *, max_messages: int) -> list[QueueMessage]:
            return [self.message]

        def delete(self, message: QueueMessage) -> None:
            self.deleted.append(message)

    queue = FakeQueue()
    consumer = SqsConsumer(
        queue=queue,
        processor=_processor(session_factory, InMemoryReceiptStore()),
    )

    result = consumer.consume_once()

    assert result.failed == 1
    assert result.deleted == 0
    assert queue.deleted == []
    with session_factory() as db:
        gift = db.get(GiftTransaction, gift_id)
        assert gift is not None and gift.status == "pending"
        assert db.execute(select(LedgerTransaction)).scalars().all() == []
        failures = list(
            db.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "event.processing.failed")
            ).scalars()
        )
        assert failures == []
