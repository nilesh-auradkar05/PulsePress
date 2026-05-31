# ADR-0012-ledger-transactions-over-cross-row-check — Ledger transactions over cross-row CHECK

Status: Accepted for Phase 1.

## Context

The three-way money split (author / platform / tax) must always balance. A natural-but-wrong
instinct is to put a balance CHECK on `ledger_entries` — but a PostgreSQL row-level CHECK cannot
sum sibling rows, so it cannot express "the three entries for a transaction sum to the total."

## Decision

- **`ledger_transactions`** stores one balanced row per paid transaction and **owns the CHECK
  constraints** (`apps/api/app/models/commerce.py`):
  - `author_net_cents + platform_fee_cents + tax_cents = total_charged_cents`
  - `principal_amount_cents + tax_cents = total_charged_cents`
  - `UNIQUE(source_type, source_id)` prevents duplicate transactions.
- **`ledger_entries`** materializes exactly three rows (`author`, `platform`, `tax`) with
  `UNIQUE(ledger_transaction_id, account)`; it carries **no** cross-row balance CHECK.
- Both tables are **immutable** through application paths, enforced by a SQLAlchemy event guard
  (`apps/api/app/db/immutable.py`); the three-entry materialization is verified by worker/invariant
  tests rather than a DB-level cross-row constraint.

## Consequences

- **+** Balance is enforced where it is expressible (single row) and verifiable in tests where it is
  not (across rows).
- **+** Immutability + uniqueness make duplicate or tampered ledger writes impossible via the app.
- **−** The "exactly three entries summing to total" invariant relies on the worker writing all rows
  atomically plus tests, not a single DB constraint — acceptable and documented (CLAUDE.md §6.3).
