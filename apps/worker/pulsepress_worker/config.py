"""Worker configuration, intentionally separate from the API runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str
    mode: str
    aws_region: str
    event_bus_name: str
    queue_url: str
    receipt_bucket: str
    local_artifact_directory: str
    poll_batch_size: int
    event_lock_seconds: int
    max_event_attempts: int
    outbox_retry_base_seconds: int
    outbox_max_attempts: int
    poll_interval_seconds: float
    run_once: bool

    @classmethod
    def from_env(cls) -> WorkerSettings:
        return cls(
            database_url=os.getenv(
                "PULSEPRESS_DATABASE_URL",
                "postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress",
            ),
            mode=os.getenv("PULSEPRESS_WORKER_MODE", "local").lower(),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            event_bus_name=os.getenv("PULSEPRESS_EVENT_BUS_NAME", "pulsepress"),
            queue_url=os.getenv("PULSEPRESS_WORKER_QUEUE_URL", ""),
            receipt_bucket=os.getenv("PULSEPRESS_RECEIPT_BUCKET", ""),
            local_artifact_directory=os.getenv(
                "PULSEPRESS_LOCAL_ARTIFACT_DIRECTORY", "/tmp/pulsepress-artifacts"
            ),
            poll_batch_size=_int_env("PULSEPRESS_WORKER_POLL_BATCH_SIZE", 25),
            event_lock_seconds=_int_env("PULSEPRESS_WORKER_EVENT_LOCK_SECONDS", 300),
            max_event_attempts=_int_env("PULSEPRESS_WORKER_MAX_RECEIVE_COUNT", 5),
            outbox_retry_base_seconds=_int_env("PULSEPRESS_OUTBOX_RETRY_BASE_SECONDS", 5),
            outbox_max_attempts=_int_env("PULSEPRESS_OUTBOX_MAX_ATTEMPTS", 10),
            poll_interval_seconds=_float_env("PULSEPRESS_WORKER_POLL_INTERVAL_SECONDS", 1.0),
            run_once=os.getenv("PULSEPRESS_WORKER_RUN_ONCE", "false").lower()
            in {"1", "true", "yes"},
        )

    def validate(self) -> None:
        if self.mode not in {"local", "aws"}:
            raise RuntimeError("PULSEPRESS_WORKER_MODE must be 'local' or 'aws'")
        if self.poll_batch_size < 1 or self.poll_batch_size > 100:
            raise RuntimeError("PULSEPRESS_WORKER_POLL_BATCH_SIZE must be between 1 and 100")
        if self.event_lock_seconds < 1:
            raise RuntimeError("PULSEPRESS_WORKER_EVENT_LOCK_SECONDS must be positive")
        if self.max_event_attempts < 1 or self.max_event_attempts > 100:
            raise RuntimeError("PULSEPRESS_WORKER_MAX_RECEIVE_COUNT must be between 1 and 100")
        if self.outbox_retry_base_seconds < 1:
            raise RuntimeError("PULSEPRESS_OUTBOX_RETRY_BASE_SECONDS must be positive")
        if self.outbox_max_attempts < 1 or self.outbox_max_attempts > 100:
            raise RuntimeError("PULSEPRESS_OUTBOX_MAX_ATTEMPTS must be between 1 and 100")
        if self.poll_interval_seconds <= 0:
            raise RuntimeError("PULSEPRESS_WORKER_POLL_INTERVAL_SECONDS must be positive")
        if self.mode == "aws":
            missing = [
                name
                for name, value in {
                    "PULSEPRESS_WORKER_QUEUE_URL": self.queue_url,
                    "PULSEPRESS_RECEIPT_BUCKET": self.receipt_bucket,
                    "PULSEPRESS_EVENT_BUS_NAME": self.event_bus_name,
                }.items()
                if not value
            ]
            if missing:
                raise RuntimeError("Missing required AWS worker settings: " + ", ".join(missing))
