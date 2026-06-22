"""API-level idempotency for commerce mutations (CLAUDE.md §5.1, SPEC §11).

A commerce write claims an ``idempotency_keys`` row keyed by ``(user_id, key)``
within the same transaction as the business write. Replays of the same key +
same request return the stored response; the same key with a different request
body is a conflict. Because the idempotency row is only committed alongside the
business write, a *failed* request leaves no cached response — a retry can still
succeed.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IdempotencyKey
from app.services.errors import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyKeyRequired,
)

MIN_KEY_LENGTH = 16
LOCK_TTL = timedelta(seconds=60)


@dataclass(frozen=True)
class Replay:
    """A previously-stored response to return verbatim."""

    status_code: int
    body: dict


def _fingerprint(request: dict) -> str:
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _locked_until() -> datetime:
    return datetime.now(UTC) + LOCK_TTL


def _handle_existing(existing: IdempotencyKey, *, request_hash: str) -> Replay | IdempotencyKey:
    if existing.request_hash != request_hash:
        raise IdempotencyConflict(
            "This Idempotency-Key was previously used with a different request body."
        )
    if existing.response_status is not None:
        return Replay(existing.response_status, existing.response_body or {})

    now = datetime.now(UTC)
    if existing.locked_until is not None and existing.locked_until > now:
        raise IdempotencyInFlight("This Idempotency-Key is already processing. Retry shortly.")

    existing.locked_until = _locked_until()
    return existing


def claim(
    db: Session,
    *,
    user_id: uuid.UUID,
    key: str | None,
    request: dict,
) -> Replay | IdempotencyKey:
    """Return a :class:`Replay` for a known key, else a fresh (flushed) record.

    Raises :class:`IdempotencyKeyRequired` when the header is missing/too short,
    and :class:`IdempotencyConflict` when the key was used with a different body.
    """
    if not key or len(key) < MIN_KEY_LENGTH:
        raise IdempotencyKeyRequired(
            f"Idempotency-Key header is required (min length {MIN_KEY_LENGTH})."
        )

    request_hash = _fingerprint(request)
    record = IdempotencyKey(
        user_id=user_id,
        key=key,
        request_hash=request_hash,
        locked_until=_locked_until(),
    )
    try:
        with db.begin_nested():
            db.add(record)
            db.flush()
        return record
    except IntegrityError:
        existing = db.execute(
            select(IdempotencyKey)
            .where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == key,
            )
            .with_for_update()
        ).scalar_one()
        return _handle_existing(existing, request_hash=request_hash)


def record_response(record: IdempotencyKey, *, status_code: int, body: dict) -> None:
    record.response_status = status_code
    record.response_body = body
    record.locked_until = None
