"""Application-level immutability guard.

Some tables are append-only by contract (CLAUDE.md §6.3/§8, SPEC §6): once a
row is written it must never be updated or deleted through application paths.
We enforce this centrally with SQLAlchemy mapper events that raise on any
UPDATE/DELETE of a registered model. INSERTs are unaffected.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import DDL, MetaData, event

IMMUTABLE_TABLES = (
    "ledger_transactions",
    "ledger_entries",
    "post_versions",
    "reconciliation_log",
)

CREATE_IMMUTABLE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION pulsepress_block_immutable_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION USING
        ERRCODE = '55000',
        MESSAGE = TG_TABLE_NAME || ' is immutable and cannot be updated or deleted';
END;
$$ LANGUAGE plpgsql
"""

DROP_IMMUTABLE_FUNCTION_SQL = "DROP FUNCTION IF EXISTS pulsepress_block_immutable_mutation()"

CREATE_IMMUTABLE_TRIGGERS_SQL = (
    "DO $$\nBEGIN\n"
    + "\n".join(
        f"""
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'block_immutable_mutation_{table}'
    ) THEN
        CREATE TRIGGER block_immutable_mutation_{table}
        BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION pulsepress_block_immutable_mutation();
    END IF;
"""
        for table in IMMUTABLE_TABLES
    )
    + "END $$"
)

DROP_IMMUTABLE_TRIGGERS_SQL = (
    "DO $$\nBEGIN\n"
    + "\n".join(
        f"    DROP TRIGGER IF EXISTS block_immutable_mutation_{table} ON {table};"
        for table in IMMUTABLE_TABLES
    )
    + "\nEND $$"
)


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


def register_db_immutable_triggers(metadata: MetaData) -> None:
    """Create PostgreSQL triggers for append-only tables when metadata creates tables."""
    event.listen(
        metadata,
        "before_create",
        DDL(CREATE_IMMUTABLE_FUNCTION_SQL).execute_if(dialect="postgresql"),
    )
    event.listen(
        metadata,
        "after_create",
        DDL(CREATE_IMMUTABLE_TRIGGERS_SQL).execute_if(dialect="postgresql"),
    )
    event.listen(
        metadata,
        "before_drop",
        DDL(DROP_IMMUTABLE_TRIGGERS_SQL).execute_if(dialect="postgresql"),
    )
    event.listen(
        metadata,
        "after_drop",
        DDL(DROP_IMMUTABLE_FUNCTION_SQL).execute_if(dialect="postgresql"),
    )
