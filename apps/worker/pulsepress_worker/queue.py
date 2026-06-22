"""SQS consumption semantics: delete only after a durable successful handler."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .adapters import QueueClient
from .processor import EventInProgressError, WorkerProcessor

logger = logging.getLogger("pulsepress.worker.queue")


@dataclass(frozen=True)
class ConsumeResult:
    received: int
    deleted: int
    failed: int
    in_progress: int


class SqsConsumer:
    def __init__(
        self, *, queue: QueueClient, processor: WorkerProcessor, batch_size: int = 10
    ) -> None:
        self._queue = queue
        self._processor = processor
        self._batch_size = batch_size

    def consume_once(self) -> ConsumeResult:
        received = deleted = failed = in_progress = 0
        for message in self._queue.receive(max_messages=self._batch_size):
            received += 1
            try:
                result = self._processor.process_mapping(message.body)
            except EventInProgressError:
                in_progress += 1
                # Do not delete: the visibility timeout makes SQS retry it.
                continue
            except Exception:
                failed += 1
                logger.exception("worker handler failed; leaving SQS message for retry/DLQ")
                # Do not delete: configured SQS redrive moves poison messages to DLQ.
                continue
            if result.status == "terminal":
                failed += 1
                logger.warning("terminal worker failure is awaiting SQS DLQ redrive")
                continue
            self._queue.delete(message)
            deleted += 1
        return ConsumeResult(
            received=received,
            deleted=deleted,
            failed=failed,
            in_progress=in_progress,
        )
