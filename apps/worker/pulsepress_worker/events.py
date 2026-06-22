"""Versioned event envelope parsing and worker-produced envelope construction."""

from __future__ import annotations

import datetime
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class MalformedEventError(ValueError):
    """Raised when an inbound EventBridge/SQS detail does not meet the contract."""


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _parse_uuid(value: object, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise MalformedEventError(f"{field} must be a UUID") from exc


def _parse_datetime(value: object) -> datetime.datetime:
    if not isinstance(value, str):
        raise MalformedEventError("occurred_at must be an ISO-8601 string")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MalformedEventError("occurred_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise MalformedEventError("occurred_at must include a UTC offset")
    return parsed.astimezone(datetime.UTC)


@dataclass(frozen=True)
class EventEnvelope:
    event_id: uuid.UUID
    event_type: str
    event_version: int
    occurred_at: datetime.datetime
    producer: str
    correlation_id: str
    causation_id: uuid.UUID | None
    aggregate_type: str
    aggregate_id: uuid.UUID
    payload: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> EventEnvelope:
        required = (
            "event_id",
            "event_type",
            "event_version",
            "occurred_at",
            "producer",
            "correlation_id",
            "aggregate_type",
            "aggregate_id",
            "payload",
        )
        missing = [field for field in required if field not in value]
        if missing:
            raise MalformedEventError("missing event fields: " + ", ".join(missing))

        event_type = value["event_type"]
        producer = value["producer"]
        correlation_id = value["correlation_id"]
        aggregate_type = value["aggregate_type"]
        event_version = value["event_version"]
        payload = value["payload"]
        if not isinstance(event_type, str) or not event_type:
            raise MalformedEventError("event_type must be a non-empty string")
        if not isinstance(producer, str) or not producer:
            raise MalformedEventError("producer must be a non-empty string")
        if not isinstance(aggregate_type, str) or not aggregate_type:
            raise MalformedEventError("aggregate_type must be a non-empty string")
        if not isinstance(correlation_id, str):
            raise MalformedEventError("correlation_id must be a string")
        if not isinstance(event_version, int) or event_version < 1:
            raise MalformedEventError("event_version must be a positive integer")
        if not isinstance(payload, Mapping):
            raise MalformedEventError("payload must be an object")

        causation = value.get("causation_id")
        return cls(
            event_id=_parse_uuid(value["event_id"], "event_id"),
            event_type=event_type,
            event_version=event_version,
            occurred_at=_parse_datetime(value["occurred_at"]),
            producer=producer,
            correlation_id=correlation_id,
            causation_id=_parse_uuid(causation, "causation_id") if causation is not None else None,
            aggregate_type=aggregate_type,
            aggregate_id=_parse_uuid(value["aggregate_id"], "aggregate_id"),
            payload=dict(payload),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_version": self.event_version,
            "occurred_at": self.occurred_at.isoformat(),
            "producer": self.producer,
            "correlation_id": self.correlation_id,
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": str(self.aggregate_id),
            "payload": self.payload,
        }

    @classmethod
    def malformed_from(cls, value: Mapping[str, object], error: Exception) -> EventEnvelope:
        """Produce a deterministic failure identity for a malformed SQS message.

        A raw malformed payload may not provide a valid UUID. Hashing canonical
        JSON gives redeliveries one durable processing-attempt row while keeping
        the message out of business handlers.
        """
        canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        event_id = uuid.uuid5(uuid.NAMESPACE_URL, canonical)
        raw_type = value.get("event_type")
        event_type = raw_type if isinstance(raw_type, str) and raw_type else "invalid.event"
        return cls(
            event_id=event_id,
            event_type=event_type,
            event_version=1,
            occurred_at=utcnow(),
            producer="queue",
            correlation_id="malformed-event",
            causation_id=None,
            aggregate_type="event",
            aggregate_id=event_id,
            payload={"validation_error": str(error), "raw_event": dict(value)},
        )


def worker_event(
    *,
    event_type: str,
    correlation_id: str,
    causation_id: uuid.UUID,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: dict[str, object],
) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid.uuid4(),
        event_type=event_type,
        event_version=1,
        occurred_at=utcnow(),
        producer="worker",
        correlation_id=correlation_id,
        causation_id=causation_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
    )
