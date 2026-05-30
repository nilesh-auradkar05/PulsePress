# PulsePress — Operability Layer (v1.2)

## Detection

Metrics:

- `dlq_depth`
- `outbox_pending_count`
- `outbox_oldest_pending_age_seconds`
- `worker_handler_failures_total`
- `worker_handler_duration_p95`
- `sqs_age_of_oldest_message`

## Action verbs

1. Retry: safe reset to pending.
2. Amend & retry: feature-flag-gated; requires reason and typed confirmation `AMEND <event_id>`.
3. Discard: requires reason >= 10 chars and opens reconciliation review.

## Reconciliation

Every admin action writes immutable `reconciliation_log` with before/after state.
Discarded events must be reconciled against source business rows and ledger state.
