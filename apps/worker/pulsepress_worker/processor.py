"""Idempotent SQS event processing and three-entry ledger materialization."""

from __future__ import annotations

import datetime
import logging
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .adapters import ReceiptStore
from .events import EventEnvelope, MalformedEventError, utcnow, worker_event
from .models import (
    EventProcessingAttempt,
    GiftTransaction,
    LedgerEntry,
    LedgerTransaction,
    PublicationDailyStats,
    Subscription,
)
from .outbox import enqueue_worker_event

logger = logging.getLogger("pulsepress.worker.processor")


class EventInProgressError(RuntimeError):
    """A concurrent worker owns the event lease; SQS must retry later."""


class UnsupportedEventError(ValueError):
    pass


class SourceConflictError(ValueError):
    pass


@dataclass(frozen=True)
class ProcessResult:
    status: str
    attempt_number: int


@dataclass(frozen=True)
class _Claim:
    attempt_id: uuid.UUID
    attempt_number: int


@dataclass(frozen=True)
class _Bill:
    principal_amount_cents: int
    author_net_cents: int
    platform_fee_cents: int
    tax_cents: int
    total_charged_cents: int

    @classmethod
    def from_payload(cls, *, payload: Mapping[str, object]) -> _Bill:
        raw = payload.get("bill")
        if not isinstance(raw, Mapping):
            raise ValueError("paid event requires a bill object")
        required = {
            "amount_cents": "principal_amount_cents",
            "author_net_cents": "author_net_cents",
            "platform_fee_cents": "platform_fee_cents",
            "tax_cents": "tax_cents",
            "total_charged_cents": "total_charged_cents",
        }
        parsed: dict[str, int] = {}
        for key, target in required.items():
            value = raw.get(key)
            if type(value) is not int or value < 0:
                raise ValueError(f"bill.{key} must be a non-negative integer")
            parsed[target] = value
        event_amount = payload.get("amount_cents")
        if type(event_amount) is not int or event_amount != parsed["principal_amount_cents"]:
            raise ValueError("bill.amount_cents must match payload.amount_cents")
        if (
            parsed["author_net_cents"]
            + parsed["platform_fee_cents"]
            + parsed["tax_cents"]
            != parsed["total_charged_cents"]
        ):
            raise ValueError("bill is not balanced")
        if parsed["principal_amount_cents"] + parsed["tax_cents"] != parsed["total_charged_cents"]:
            raise ValueError("bill total does not equal principal plus tax")
        return cls(**parsed)


@dataclass(frozen=True)
class _SourceEvent:
    source_type: str
    source_id: uuid.UUID
    publication_id: uuid.UUID
    currency: str
    bill: _Bill | None


@dataclass(frozen=True)
class _Receipt:
    key: str
    contents: dict[str, object]


class WorkerProcessor:
    """Processes a domain envelope exactly once after a durable claim.

    The claim is committed before the handler starts. This deliberately makes
    SQS redelivery observe an in-flight lease instead of executing the handler
    a second time. Durable source state, the success marker, and the derived
    ``ledger.transaction.recorded`` outbox event commit together.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        receipt_store: ReceiptStore,
        event_lock_seconds: int = 300,
        max_event_attempts: int = 5,
    ) -> None:
        self._session_factory = session_factory
        self._receipt_store = receipt_store
        self._event_lock_seconds = event_lock_seconds
        self._max_event_attempts = max_event_attempts

    def process_mapping(
        self, value: Mapping[str, object]
    ) -> ProcessResult:
        try:
            event = EventEnvelope.from_mapping(value)
        except MalformedEventError as exc:
            event = EventEnvelope.malformed_from(value, exc)
            return self._process(event, initial_error=exc)
        return self._process(event)

    def _process(
        self,
        event: EventEnvelope,
        *,
        initial_error: Exception | None = None,
    ) -> ProcessResult:
        claim = self._claim(event)
        if isinstance(claim, str):
            return ProcessResult(status=claim, attempt_number=0)

        try:
            if initial_error is not None:
                raise initial_error
            if event.event_version != 1:
                raise UnsupportedEventError(
                    f"unsupported {event.event_type} event version {event.event_version}"
                )
            receipt = self._prepare_receipt(event)
            # At-least-once recovery contract: the receipt is stored before the
            # handler DB transaction commits.  On a hard crash after this PUT but
            # before the ledger commit the attempt row stays "started" until the
            # lease expires (locked_until).  On the next delivery _claim re-claims
            # the row, and both the idempotent receipt store (S3 IfNoneMatch:*/
            # filesystem open("x")) and UNIQUE(source_type, source_id) on
            # ledger_transactions ensure the retry produces exactly-once durable
            # effects with no double charge.
            receipt_key = self._store_prepared_receipt(receipt)
            with self._session_factory() as db:
                with db.begin():
                    attempt = db.execute(
                        select(EventProcessingAttempt)
                        .where(EventProcessingAttempt.id == claim.attempt_id)
                        .with_for_update()
                    ).scalar_one()
                    if attempt.status != "started":
                        raise EventInProgressError(f"event {event.event_id} is no longer claimed")

                    self._dispatch(db, event, receipt_key=receipt_key)
                    attempt.status = "succeeded"
                    attempt.error_message = None
                    attempt.finished_at = utcnow()
                    attempt.locked_until = None
            return ProcessResult(status="succeeded", attempt_number=claim.attempt_number)
        except EventInProgressError:
            raise
        except Exception as exc:
            self._record_failure(
                event,
                claim=claim,
                error=exc,
                terminal=claim.attempt_number >= self._max_event_attempts,
            )
            raise

    def _claim(self, event: EventEnvelope) -> _Claim | str:
        now = utcnow()
        lock_until = now + datetime.timedelta(seconds=self._event_lock_seconds)
        with self._session_factory() as db:
            with db.begin():
                created_id = db.execute(
                    insert(EventProcessingAttempt)
                    .values(
                        event_id=event.event_id,
                        event_type=event.event_type,
                        status="started",
                        attempt_number=1,
                        locked_until=lock_until,
                    )
                    .on_conflict_do_nothing(index_elements=[EventProcessingAttempt.event_id])
                    .returning(EventProcessingAttempt.id)
                ).scalar_one_or_none()
                if created_id is not None:
                    return _Claim(attempt_id=created_id, attempt_number=1)

                attempt = db.execute(
                    select(EventProcessingAttempt)
                    .where(EventProcessingAttempt.event_id == event.event_id)
                    .with_for_update()
                ).scalar_one()
                if attempt.status == "succeeded":
                    return "duplicate"
                if attempt.terminal_at is not None:
                    return "terminal"
                if attempt.status == "started" and (
                    attempt.locked_until is None or attempt.locked_until > now
                ):
                    raise EventInProgressError(f"event {event.event_id} is already in progress")

                attempt.status = "started"
                attempt.attempt_number += 1
                attempt.error_message = None
                attempt.finished_at = None
                attempt.locked_until = lock_until
                return _Claim(attempt_id=attempt.id, attempt_number=attempt.attempt_number)

    def _prepare_receipt(self, event: EventEnvelope) -> _Receipt | None:
        source = self._source_event(event)
        if source is None:
            return None

        with self._session_factory() as db:
            with db.begin():
                self._validate_source(db, source=source)
                if source.bill is not None:
                    self._ensure_ledger_event_identity(db, source=source, event=event)

        if source.bill is None:
            return None

        key = f"receipts/{source.source_type}/{source.source_id}/{event.event_id}.json"
        return _Receipt(
            key=key,
            contents={
                "receipt_version": 1,
                "source_type": source.source_type,
                "source_id": str(source.source_id),
                "source_event_id": str(event.event_id),
                "publication_id": str(source.publication_id),
                "currency": source.currency,
                "bill": {
                    "amount_cents": source.bill.principal_amount_cents,
                    "author_net_cents": source.bill.author_net_cents,
                    "platform_fee_cents": source.bill.platform_fee_cents,
                    "tax_cents": source.bill.tax_cents,
                    "total_charged_cents": source.bill.total_charged_cents,
                },
            },
        )

    def _store_prepared_receipt(self, receipt: _Receipt | None) -> str | None:
        if receipt is None:
            return None
        return self._receipt_store.put_receipt(key=receipt.key, contents=receipt.contents)

    def _source_event(self, event: EventEnvelope) -> _SourceEvent | None:
        if event.event_type == "subscription.created":
            tier = event.payload.get("tier")
            source_id = self._payload_uuid(event.payload, "subscription_id")
            publication_id = self._payload_uuid(event.payload, "publication_id")
            currency = self._currency(event.payload)
            if tier == "free":
                if event.payload.get("bill") is not None:
                    raise ValueError("free subscription event must not include a bill")
                return _SourceEvent(
                    source_type="subscription",
                    source_id=source_id,
                    publication_id=publication_id,
                    currency=currency,
                    bill=None,
                )
            if tier != "paid":
                raise ValueError("subscription.created tier must be free or paid")
            return _SourceEvent(
                source_type="subscription",
                source_id=source_id,
                publication_id=publication_id,
                currency=currency,
                bill=_Bill.from_payload(payload=event.payload),
            )
        elif event.event_type == "gift.sent":
            return _SourceEvent(
                source_type="gift",
                source_id=self._payload_uuid(event.payload, "gift_id"),
                publication_id=self._payload_uuid(event.payload, "publication_id"),
                currency=self._currency(event.payload),
                bill=_Bill.from_payload(payload=event.payload),
            )
        return None

    def _dispatch(self, db: Session, event: EventEnvelope, *, receipt_key: str | None) -> None:
        if event.event_type == "subscription.created":
            self._handle_subscription_created(db, event, receipt_key=receipt_key)
            return
        if event.event_type == "gift.sent":
            self._handle_gift_sent(db, event, receipt_key=receipt_key)
            return
        if event.event_type in {
            "subscription.tier_changed",
            "subscription.canceled",
            "ledger.transaction.recorded",
            "event.processing.failed",
        }:
            # These state transitions have no S4 ledger work. Marking the
            # delivery succeeded prevents the worker's own outbox events from
            # becoming poison messages while future sprint handlers are added.
            return
        raise UnsupportedEventError(f"no handler for event type {event.event_type}")

    def _handle_subscription_created(
        self, db: Session, event: EventEnvelope, *, receipt_key: str | None
    ) -> None:
        subscription_id = self._payload_uuid(event.payload, "subscription_id")
        publication_id = self._payload_uuid(event.payload, "publication_id")
        subscription = db.execute(
            select(Subscription).where(Subscription.id == subscription_id).with_for_update()
        ).scalar_one_or_none()
        source = self._source_event(event)
        if source is None:
            raise ValueError("subscription event source is missing")
        self._validate_subscription_source(subscription, source=source)

        tier = event.payload.get("tier")
        if tier == "free":
            self._increment_stats(db, event=event, publication_id=publication_id, subscribers=1)
            return
        if tier != "paid" or receipt_key is None:
            raise ValueError("paid subscription event requires a stored receipt")

        bill = _Bill.from_payload(payload=event.payload)
        created = self._write_ledger(
            db,
            event=event,
            source_type="subscription",
            source_id=subscription_id,
            publication_id=publication_id,
            currency=self._currency(event.payload),
            bill=bill,
            receipt_key=receipt_key,
        )
        if created:
            self._increment_stats(
                db,
                event=event,
                publication_id=publication_id,
                subscribers=1,
                gross_revenue_cents=bill.total_charged_cents,
                author_net_cents=bill.author_net_cents,
                platform_fees_cents=bill.platform_fee_cents,
                tax_collected_cents=bill.tax_cents,
            )

    def _handle_gift_sent(
        self, db: Session, event: EventEnvelope, *, receipt_key: str | None) -> None:
        gift_id = self._payload_uuid(event.payload, "gift_id")
        publication_id = self._payload_uuid(event.payload, "publication_id")
        gift = db.execute(
            select(GiftTransaction).where(GiftTransaction.id == gift_id).with_for_update()
        ).scalar_one_or_none()
        source = self._source_event(event)
        if source is None:
            raise ValueError("gift event source is missing")
        gift = self._validate_gift_source(gift, source=source)
        if receipt_key is None:
            raise ValueError("gift.sent requires a stored receipt")
        bill = _Bill.from_payload(payload=event.payload)
        created = self._write_ledger(
            db,
            event=event,
            source_type="gift",
            source_id=gift_id,
            publication_id=publication_id,
            currency=self._currency(event.payload),
            bill=bill,
            receipt_key=receipt_key,
        )
        if created:
            gift.status = "processed"
            self._increment_stats(
                db,
                event=event,
                publication_id=publication_id,
                gifts=1,
                gross_revenue_cents=bill.total_charged_cents,
                author_net_cents=bill.author_net_cents,
                platform_fees_cents=bill.platform_fee_cents,
                tax_collected_cents=bill.tax_cents,
            )

    def _write_ledger(
        self,
        db: Session,
        *,
        event: EventEnvelope,
        source_type: str,
        source_id: uuid.UUID,
        publication_id: uuid.UUID,
        currency: str,
        bill: _Bill,
        receipt_key: str,
    ) -> bool:
        existing = db.execute(
            select(LedgerTransaction).where(
                LedgerTransaction.source_type == source_type,
                LedgerTransaction.source_id == source_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.source_event_id != event.event_id:
                raise SourceConflictError(
                    f"{source_type} {source_id} already has a ledger transaction from another event"
                )
            return False

        transaction = LedgerTransaction(
            publication_id=publication_id,
            source_type=source_type,
            source_id=source_id,
            source_event_id=event.event_id,
            principal_amount_cents=bill.principal_amount_cents,
            author_net_cents=bill.author_net_cents,
            platform_fee_cents=bill.platform_fee_cents,
            tax_cents=bill.tax_cents,
            total_charged_cents=bill.total_charged_cents,
            currency=currency,
        )
        db.add(transaction)
        db.flush()

        entries = [
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                publication_id=publication_id,
                account="author",
                amount_cents=bill.author_net_cents,
            ),
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                publication_id=publication_id,
                account="platform",
                amount_cents=bill.platform_fee_cents,
            ),
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                publication_id=publication_id,
                account="tax",
                amount_cents=bill.tax_cents,
            ),
        ]
        db.add_all(entries)
        db.flush()

        enqueue_worker_event(
            db,
            worker_event(
                event_type="ledger.transaction.recorded",
                correlation_id=event.correlation_id,
                causation_id=event.event_id,
                aggregate_type="ledger",
                aggregate_id=transaction.id,
                payload={
                    "ledger_transaction_id": str(transaction.id),
                    "source_type": source_type,
                    "source_id": str(source_id),
                    "publication_id": str(publication_id),
                    "principal_amount_cents": bill.principal_amount_cents,
                    "author_net_cents": bill.author_net_cents,
                    "platform_fee_cents": bill.platform_fee_cents,
                    "tax_cents": bill.tax_cents,
                    "total_charged_cents": bill.total_charged_cents,
                    "entry_ids": [str(entry.id) for entry in entries],
                    "receipt_artifact_key": receipt_key,
                },
            ),
        )
        return True

    def _validate_source(self, db: Session, *, source: _SourceEvent) -> None:
        if source.source_type == "subscription":
            subscription = db.execute(
                select(Subscription).where(Subscription.id == source.source_id).with_for_update()
            ).scalar_one_or_none()
            self._validate_subscription_source(subscription, source=source)
            return
        if source.source_type == "gift":
            gift = db.execute(
                select(GiftTransaction)
                .where(GiftTransaction.id == source.source_id)
                .with_for_update()
            ).scalar_one_or_none()
            self._validate_gift_source(gift, source=source)
            return
        raise UnsupportedEventError(f"unsupported ledger source {source.source_type}")

    @staticmethod
    def _validate_subscription_source(
        subscription: Subscription | None, *, source: _SourceEvent
    ) -> Subscription:
        if subscription is None or subscription.publication_id != source.publication_id:
            raise SourceConflictError("subscription source does not match event publication")
        expected_amount = source.bill.principal_amount_cents if source.bill else 0
        if subscription.charged_amount_cents != expected_amount:
            raise SourceConflictError("subscription charged amount does not match event")
        if subscription.charged_currency != source.currency:
            raise SourceConflictError("subscription charged currency does not match event")
        if subscription.status not in {"active", "canceled", "expired"}:
            raise SourceConflictError("subscription source has an invalid status")
        return subscription

    @staticmethod
    def _validate_gift_source(
        gift: GiftTransaction | None, *, source: _SourceEvent
    ) -> GiftTransaction:
        if gift is None or gift.publication_id != source.publication_id:
            raise SourceConflictError("gift source does not match event publication")
        if source.bill is None:
            raise ValueError("gift.sent requires a bill")
        if gift.amount_cents != source.bill.principal_amount_cents:
            raise SourceConflictError("gift amount does not match event bill")
        if gift.currency != source.currency:
            raise SourceConflictError("gift currency does not match event")
        if gift.status not in {"pending", "processed"}:
            raise SourceConflictError("gift source has an invalid status")
        return gift

    @staticmethod
    def _ensure_ledger_event_identity(
        db: Session, *, source: _SourceEvent, event: EventEnvelope
    ) -> None:
        existing = db.execute(
            select(LedgerTransaction).where(
                LedgerTransaction.source_type == source.source_type,
                LedgerTransaction.source_id == source.source_id,
            )
        ).scalar_one_or_none()
        if existing is not None and existing.source_event_id != event.event_id:
            raise SourceConflictError(
                f"{source.source_type} {source.source_id} already has a ledger transaction "
                "from another event"
            )

    def _increment_stats(
        self,
        db: Session,
        *,
        event: EventEnvelope,
        publication_id: uuid.UUID,
        subscribers: int = 0,
        gifts: int = 0,
        gross_revenue_cents: int = 0,
        author_net_cents: int = 0,
        platform_fees_cents: int = 0,
        tax_collected_cents: int = 0,
    ) -> None:
        stat_date = event.occurred_at.date()
        db.execute(
            insert(PublicationDailyStats)
            .values(
                publication_id=publication_id,
                stat_date=stat_date,
                subscriber_count=subscribers,
                gift_count=gifts,
                post_count=0,
                gross_revenue_cents=gross_revenue_cents,
                author_net_cents=author_net_cents,
                platform_fees_cents=platform_fees_cents,
                tax_collected_cents=tax_collected_cents,
            )
            .on_conflict_do_update(
                constraint="publication_date_unique",
                set_={
                    "subscriber_count": PublicationDailyStats.subscriber_count + subscribers,
                    "gift_count": PublicationDailyStats.gift_count + gifts,
                    "gross_revenue_cents": (
                        PublicationDailyStats.gross_revenue_cents + gross_revenue_cents
                    ),
                    "author_net_cents": PublicationDailyStats.author_net_cents + author_net_cents,
                    "platform_fees_cents": (
                        PublicationDailyStats.platform_fees_cents + platform_fees_cents
                    ),
                    "tax_collected_cents": (
                        PublicationDailyStats.tax_collected_cents + tax_collected_cents
                    ),
                },
            )
        )

    def _record_failure(
        self, event: EventEnvelope, *, claim: _Claim, error: Exception, terminal: bool
    ) -> None:
        message = str(error)[:2048] or type(error).__name__
        try:
            with self._session_factory() as db:
                with db.begin():
                    attempt = db.execute(
                        select(EventProcessingAttempt)
                        .where(EventProcessingAttempt.id == claim.attempt_id)
                        .with_for_update()
                    ).scalar_one()
                    if attempt.status == "succeeded":
                        return
                    attempt.status = "failed"
                    attempt.error_message = message
                    attempt.finished_at = utcnow()
                    attempt.locked_until = None
                    if terminal:
                        attempt.terminal_at = utcnow()
                        if attempt.failure_event_emitted_at is None:
                            enqueue_worker_event(
                                db,
                                worker_event(
                                    event_type="event.processing.failed",
                                    correlation_id=event.correlation_id,
                                    causation_id=event.event_id,
                                    aggregate_type="event",
                                    aggregate_id=event.event_id,
                                    payload={
                                        "event_id": str(event.event_id),
                                        "event_type": event.event_type,
                                        "event_version": event.event_version,
                                        "handler": self._handler_name(event),
                                        "attempt_number": claim.attempt_number,
                                        "error_code": type(error).__name__,
                                        "error_message": message,
                                        "failed_at": utcnow().isoformat(),
                                        "terminal": True,
                                    },
                                ),
                            )
                            attempt.failure_event_emitted_at = utcnow()
        except Exception:
            logger.exception("failed to persist worker failure for event %s", event.event_id)

    @staticmethod
    def _handler_name(event: EventEnvelope) -> str:
        return f"{event.event_type}.v{event.event_version}"

    @staticmethod
    def _payload_uuid(payload: Mapping[str, object], field: str) -> uuid.UUID:
        value = payload.get(field)
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"payload.{field} must be a UUID") from exc

    @staticmethod
    def _currency(payload: Mapping[str, object]) -> str:
        currency = payload.get("currency")
        if not isinstance(currency, str) or len(currency) != 3 or currency.upper() != currency:
            raise ValueError("payload.currency must be a three-letter uppercase code")
        return currency
