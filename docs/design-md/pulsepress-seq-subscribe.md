# PulsePress — Paid Subscribe Sequence (v1.2)

1. Subscriber selects a plan and sends `POST /v1/subscriptions` with `Idempotency-Key`.
2. API validates JWT, no self-subscribe, active plan, no active duplicate subscription.
3. API computes integer-cent bill breakdown once.
4. Same DB transaction writes `subscriptions`, `idempotency_keys`, and `outbox_events(subscription.created)`.
5. API returns transparent bill breakdown.
6. Outbox poller publishes to EventBridge and marks published.
7. EventBridge routes to SQS.
8. Worker dedupes by `event_id`.
9. Worker writes `ledger_transactions` + three `ledger_entries` atomically for paid plans.
10. Worker updates stats, stores receipt in S3, invalidates Redis, emits `ledger.transaction.recorded`.
11. Dashboard/read models update through Redis/SSE.

Free subscription follows the same API idempotency/outbox path but skips ledger writes.
