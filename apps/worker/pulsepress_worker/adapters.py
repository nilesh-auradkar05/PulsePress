"""Injectable EventBridge, S3 receipt, and SQS adapters.

Tests and local execution use the deterministic in-memory/filesystem adapters.
AWS adapters require explicit ``PULSEPRESS_WORKER_MODE=aws`` selection and are
never constructed by tests.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .events import EventEnvelope


class EventPublishError(RuntimeError):
    pass


class ReceiptStoreError(RuntimeError):
    pass


class EventPublisher(Protocol):
    def publish(self, event: EventEnvelope) -> None: ...


class ReceiptStore(Protocol):
    def put_receipt(self, *, key: str, contents: dict[str, object]) -> str: ...


@dataclass(frozen=True)
class QueueMessage:
    receipt_handle: str
    body: Mapping[str, object]
    receive_count: int = 1


class QueueClient(Protocol):
    def receive(self, *, max_messages: int) -> Iterable[QueueMessage]: ...

    def delete(self, message: QueueMessage) -> None: ...


class LocalEventBridgePublisher:
    """Captures envelopes for deterministic tests and local one-shot runs."""

    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    def publish(self, event: EventEnvelope) -> None:
        self.published.append(event)


class Boto3EventBridgePublisher:
    def __init__(self, *, client: Any, event_bus_name: str) -> None:
        self._client = client
        self._event_bus_name = event_bus_name

    def publish(self, event: EventEnvelope) -> None:
        response = self._client.put_events(
            Entries=[
                {
                    "EventBusName": self._event_bus_name,
                    "Source": (
                        "pulsepress.worker" if event.producer == "worker" else "pulsepress.api"
                    ),
                    "DetailType": event.event_type,
                    "Detail": json.dumps(event.as_dict(), separators=(",", ":"), default=str),
                }
            ]
        )
        entries = response.get("Entries", [])
        if response.get("FailedEntryCount", 0) or any(
            entry.get("ErrorCode") for entry in entries
        ):
            details = "; ".join(
                f"{entry.get('ErrorCode', 'unknown')}: {entry.get('ErrorMessage', '')}"
                for entry in entries
            )
            raise EventPublishError(f"EventBridge rejected event {event.event_id}: {details}")


class InMemoryReceiptStore:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.objects: dict[str, dict[str, object]] = {}

    def put_receipt(self, *, key: str, contents: dict[str, object]) -> str:
        if self.fail:
            raise ReceiptStoreError("simulated receipt storage failure")
        existing = self.objects.get(key)
        if existing is not None:
            if existing != contents:
                raise ReceiptStoreError(f"immutable receipt conflict for {key}")
            return key
        self.objects[key] = contents
        return key


class FilesystemReceiptStore:
    """Local deterministic receipt store, used only outside AWS mode."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def put_receipt(self, *, key: str, contents: dict[str, object]) -> str:
        serialized = json.dumps(contents, indent=2, sort_keys=True) + "\n"
        path = self._root / key
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as receipt_file:
                receipt_file.write(serialized)
        except FileExistsError:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ReceiptStoreError(f"unable to read existing receipt {key}: {exc}") from exc
            if existing != contents:
                raise ReceiptStoreError(f"immutable receipt conflict for {key}") from None
        except OSError as exc:
            raise ReceiptStoreError(f"unable to write receipt {key}: {exc}") from exc
        return key


class S3ReceiptStore:
    def __init__(self, *, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put_receipt(self, *, key: str, contents: dict[str, object]) -> str:
        serialized = json.dumps(contents, indent=2, sort_keys=True).encode()
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=serialized,
                ContentType="application/json",
                IfNoneMatch="*",
            )
        except Exception as exc:  # AWS exceptions are SDK-specific.
            if _is_precondition_failure(exc):
                if self._existing_contents_match(key=key, expected=contents):
                    return key
                raise ReceiptStoreError(f"immutable receipt conflict for {key}") from exc
            raise ReceiptStoreError(f"unable to store receipt {key}: {exc}") from exc
        return key

    def _existing_contents_match(self, *, key: str, expected: dict[str, object]) -> bool:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"].read()
            if isinstance(body, bytes):
                payload = body.decode()
            else:
                payload = str(body)
            return json.loads(payload) == expected
        except Exception:
            return False


class Boto3SqsQueue:
    def __init__(self, *, client: Any, queue_url: str) -> None:
        self._client = client
        self._queue_url = queue_url

    def receive(self, *, max_messages: int) -> Iterable[QueueMessage]:
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=10,
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in response.get("Messages", []):
            try:
                raw = json.loads(message["Body"])
            except (TypeError, json.JSONDecodeError):
                raw = {"raw_body": message.get("Body")}
            # EventBridge-to-SQS wraps the domain envelope in ``detail``.
            candidate = raw.get("detail", raw)
            if isinstance(candidate, dict):
                body = {str(key): value for key, value in candidate.items()}
            else:
                body = {"raw_body": raw}
            yield QueueMessage(
                receipt_handle=message["ReceiptHandle"],
                body=body,
                receive_count=_receive_count(message),
            )

    def delete(self, message: QueueMessage) -> None:
        self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=message.receipt_handle)


def build_boto3_client(service_name: str, *, region_name: str) -> Any:
    """Import boto3 lazily so local/test paths never initialise AWS SDK state."""
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("boto3 is required for PULSEPRESS_WORKER_MODE=aws") from exc
    return boto3.client(service_name, region_name=region_name)


def _is_precondition_failure(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return False
    error = response.get("Error")
    return isinstance(error, Mapping) and error.get("Code") in {"PreconditionFailed", "412"}


def _receive_count(message: Mapping[str, object]) -> int:
    attributes = message.get("Attributes")
    if not isinstance(attributes, Mapping):
        return 1
    try:
        return max(1, int(attributes.get("ApproximateReceiveCount", 1)))
    except (TypeError, ValueError):
        return 1
