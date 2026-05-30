# PulsePress — ER / Domain Model (v1.2)

## Table count

17 Phase-1 tables.

## Identity

- `users`

## Publishing

- `publications`
- `posts`
- `post_versions`
- `newsletter_sends`

## Commerce

- `subscription_plans`
- `subscriptions`
- `gift_transactions`
- `ledger_transactions`
- `ledger_entries`

## Reliability kernel

- `outbox_events`
- `idempotency_keys`
- `event_processing_attempts`

## Read models

- `publication_daily_stats`
- `notification_events`
- `user_feed_events`

## Operability

- `reconciliation_log`

## Critical invariants

- `ledger_transactions` owns row-level money CHECK constraints.
- `ledger_entries` has one row per account: author, platform, tax.
- `UNIQUE(ledger_transaction_id, account)` prevents duplicate account rows.
- Worker writes `ledger_transactions` and three `ledger_entries` in one transaction.
- `idempotency_keys UNIQUE(user_id, key)`.
- `subscriptions` has partial unique active subscriber/publication constraint.
- `post_versions` and ledger tables are immutable.
- `user_feed_events` provides durable per-reader feed rows.
