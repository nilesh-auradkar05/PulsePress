# PulsePress — Component / Bounded Context View (v1.2)

## Two write-shapes

### Publishing context — content-shaped

- Publications and posts are authenticated CRUD.
- No idempotency key for normal publication/post CRUD.
- No outbox events for normal CRUD.
- No ledger writes.
- Exception: `publishPost` writes a `post_versions` snapshot and emits `post.published`.

### Commerce context — money-shaped

- `createSubscription`, `changeTier`, `cancelSubscription`, `sendGift`, and admin recovery verbs require `Idempotency-Key`.
- Commerce writes create business state plus outbox event atomically.
- Worker, not API, creates ledger transactions/entries.

## Shared backbone

Both commerce writes and `publishPost` feed the same outbox → EventBridge → SQS → worker path.

## Read/fanout

- `publication_daily_stats` supports dashboard analytics.
- `notification_events` supports publication/dashboard activity.
- `user_feed_events` supports durable reader feed and reader SSE.
