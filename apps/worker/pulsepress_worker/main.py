"""Worker service entrypoint for local and explicitly configured AWS modes."""

from __future__ import annotations

import logging
import time

from .adapters import (
    Boto3EventBridgePublisher,
    Boto3SqsQueue,
    FilesystemReceiptStore,
    LocalEventBridgePublisher,
    S3ReceiptStore,
    build_boto3_client,
)
from .config import WorkerSettings
from .db import build_session_factory
from .outbox import OutboxPoller
from .processor import WorkerProcessor
from .queue import SqsConsumer

logger = logging.getLogger("pulsepress.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = WorkerSettings.from_env()
    settings.validate()
    session_factory = build_session_factory(settings.database_url)

    if settings.mode == "local":
        publisher = LocalEventBridgePublisher()
        processor = WorkerProcessor(
            session_factory=session_factory,
            receipt_store=FilesystemReceiptStore(settings.local_artifact_directory),
            event_lock_seconds=settings.event_lock_seconds,
            max_event_attempts=settings.max_event_attempts,
        )
        poller = OutboxPoller(
            session_factory=session_factory,
            publisher=publisher,
            batch_size=settings.poll_batch_size,
            retry_base_seconds=settings.outbox_retry_base_seconds,
            max_attempts=settings.outbox_max_attempts,
        )
        _run_local(
            poller=poller,
            processor=processor,
            publisher=publisher,
            run_once=settings.run_once,
        )
        return

    eventbridge = build_boto3_client("events", region_name=settings.aws_region)
    sqs = build_boto3_client("sqs", region_name=settings.aws_region)
    s3 = build_boto3_client("s3", region_name=settings.aws_region)
    poller = OutboxPoller(
        session_factory=session_factory,
        publisher=Boto3EventBridgePublisher(
            client=eventbridge,
            event_bus_name=settings.event_bus_name,
        ),
        batch_size=settings.poll_batch_size,
        retry_base_seconds=settings.outbox_retry_base_seconds,
        max_attempts=settings.outbox_max_attempts,
    )
    processor = WorkerProcessor(
        session_factory=session_factory,
        receipt_store=S3ReceiptStore(client=s3, bucket=settings.receipt_bucket),
        event_lock_seconds=settings.event_lock_seconds,
        max_event_attempts=settings.max_event_attempts,
    )
    consumer = SqsConsumer(
        queue=Boto3SqsQueue(client=sqs, queue_url=settings.queue_url),
        processor=processor,
        batch_size=min(settings.poll_batch_size, 10),
    )
    _run_aws(
        poller=poller,
        consumer=consumer,
        run_once=settings.run_once,
        interval_seconds=settings.poll_interval_seconds,
    )


def _run_local(
    *,
    poller: OutboxPoller,
    processor: WorkerProcessor,
    publisher: LocalEventBridgePublisher,
    run_once: bool,
) -> None:
    while True:
        result = poller.poll_once()
        current = list(publisher.published)
        publisher.published.clear()
        for event in current:
            processor.process_mapping(event.as_dict())
        logger.info(
            "local worker cycle: claimed=%d published=%d failed=%d processed=%d",
            result.claimed,
            result.published,
            result.failed,
            len(current),
        )
        if run_once:
            return
        time.sleep(1)


def _run_aws(
    *,
    poller: OutboxPoller,
    consumer: SqsConsumer,
    run_once: bool,
    interval_seconds: float,
) -> None:
    while True:
        poll_result = poller.poll_once()
        consume_result = consumer.consume_once()
        logger.info(
            "worker cycle: outbox claimed=%d published=%d failed=%d; "
            "queue received=%d deleted=%d failed=%d in_progress=%d",
            poll_result.claimed,
            poll_result.published,
            poll_result.failed,
            consume_result.received,
            consume_result.deleted,
            consume_result.failed,
            consume_result.in_progress,
        )
        if run_once:
            return
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
