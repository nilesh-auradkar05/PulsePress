"""Application-level immutability guard.

Some tables are append-only by contract (CLAUDE.md §6.3/§8, SPEC §6): once a
row is written it must never be updated or deleted through application paths.
We enforce this centrally with SQLAlchemy mapper events that raise on any
UPDATE/DELETE of a registered model. INSERTs are unaffected.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event


class ImmutableRowError(Exception):
    """Raised when application code attempts to update or delete an immutable row."""


def _block(mapper: Any, connection: Any, target: Any) -> None:
    raise ImmutableRowError(
        f"{type(target).__name__} rows are immutable and cannot be updated or deleted"
    )


def register_immutable(*models: type) -> None:
    for model in models:
        event.listen(model, "before_update", _block)
        event.listen(model, "before_delete", _block)
