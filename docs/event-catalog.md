# PulsePress Event Catalog

**Version:** v1.1  
**Scope:** Phase 1  
**Canonical for:** event names, envelope fields, payload shape, handler invariants.

## 1. Common envelope

Every event uses this envelope:

```json
{
  "event_id": "uuid-v4",
  "event_type": "subscription.created",
  "event_version": 1,
  "occurred_at": "2026-05-28T14:30:00Z",
  "producer": "api|worker",
  "correlation_id": "request-correlation-id",
  "causation_id": "uuid-v4-or-null",
  "aggregate_type": "subscription|gift|post|newsletter|ledger|event",
  "aggregate_id": "uuid-v4",
  "payload": {}
}
```

Rules:

- Consumers dispatch on `(event_type, event_version)`.
- Every handler deduplicates by `event_id`.
- API-produced events must carry request `correlation_id`.
- Worker-emitted events must carry `causation_id` pointing to the event that caused them.
- Additive fields are non-breaking. Removed/repurposed fields require a version bump.

## 2. Events

### `post.published` v1

Producer: API `publishPost`  
Aggregate: `post`

Payload:

```json
{
  "post_id": "uuid",
  "publication_id": "uuid",
  "author_user_id": "uuid",
  "version_id": "uuid",
  "visibility": "free|paid",
  "published_at": "date-time"
}
```

Handler invariants:

- Reads newsletter content from `post_versions.version_id`, not live `posts.body`.
- Creates `newsletter_sends` row in `requested` state.
- Emits `newsletter.send.requested`.

### `newsletter.send.requested` v1

Producer: Worker  
Aggregate: `newsletter`

Payload:

```json
{
  "newsletter_send_id": "uuid",
  "post_id": "uuid",
  "publication_id": "uuid",
  "version_id": "uuid",
  "visibility": "free|paid"
}
```

Handler invariants:

- Snapshots recipients based on visibility and subscription access at handling time.
- Writes durable `user_feed_events` rows.
- Stores simulated newsletter artifact in S3.
- Emits `newsletter.sent` or `newsletter.send.failed`.

### `newsletter.sent` v1

Payload:

```json
{
  "newsletter_send_id": "uuid",
  "post_id": "uuid",
  "publication_id": "uuid",
  "recipient_count_sim": 42,
  "artifact_s3_key": "newsletters/.../artifact.html",
  "sent_at": "date-time"
}
```

### `newsletter.send.failed` v1

Payload:

```json
{
  "newsletter_send_id": "uuid",
  "post_id": "uuid",
  "publication_id": "uuid",
  "error_code": "s3_write_failed",
  "error_message": "string"
}
```

### `subscription.created` v1

Producer: API `createSubscription`  
Aggregate: `subscription`

Payload:

```json
{
  "subscription_id": "uuid",
  "subscriber_user_id": "uuid",
  "publication_id": "uuid",
  "plan_id": "uuid",
  "amount_cents": 500,
  "currency": "USD",
  "tier": "free|paid",
  "period_start": "date-time",
  "period_end": "date-time",
  "bill": {
    "amount_cents": 500,
    "author_net_cents": 450,
    "platform_fee_cents": 50,
    "tax_cents": 40,
    "total_charged_cents": 540
  }
}
```

Rules:

- `bill` is `null` for free tier.
- Free subscriptions still require API idempotency and still emit this event.
- Worker writes ledger only when `tier=paid`.

### `subscription.tier_changed` v1

Payload:

```json
{
  "subscription_id": "uuid",
  "subscriber_user_id": "uuid",
  "publication_id": "uuid",
  "old_plan_id": "uuid",
  "new_plan_id": "uuid",
  "old_amount_cents": 500,
  "new_amount_cents": 2000,
  "changed_at": "date-time"
}
```

Rules:

- Requires API idempotency.
- No new ledger transaction in Phase 1.
- Updates read models/dashboard only.

### `subscription.canceled` v1

Payload:

```json
{
  "subscription_id": "uuid",
  "subscriber_user_id": "uuid",
  "publication_id": "uuid",
  "canceled_at": "date-time",
  "access_until": "date-time"
}
```

Rules:

- Requires API idempotency.
- No refund and no ledger reversal in Phase 1.

### `gift.sent` v1

Payload:

```json
{
  "gift_id": "uuid",
  "sender_user_id": "uuid",
  "publication_id": "uuid",
  "amount_cents": 1000,
  "currency": "USD",
  "message": "optional",
  "bill": {
    "amount_cents": 1000,
    "author_net_cents": 900,
    "platform_fee_cents": 100,
    "tax_cents": 80,
    "total_charged_cents": 1080
  }
}
```

### `ledger.transaction.recorded` v1

Producer: Worker  
Aggregate: `ledger`

Payload:

```json
{
  "ledger_transaction_id": "uuid",
  "source_type": "subscription|gift",
  "source_id": "uuid",
  "publication_id": "uuid",
  "principal_amount_cents": 1000,
  "author_net_cents": 900,
  "platform_fee_cents": 100,
  "tax_cents": 80,
  "total_charged_cents": 1080,
  "entry_ids": ["uuid", "uuid", "uuid"]
}
```

Rules:

- One event per paid transaction, not per ledger entry row.
- Causation points to `subscription.created` or `gift.sent`.

### `event.processing.failed` v1

Payload:

```json
{
  "event_id": "uuid",
  "event_type": "string",
  "event_version": 1,
  "handler": "string",
  "attempt_number": 3,
  "error_code": "string",
  "error_message": "string",
  "failed_at": "date-time"
}
```

Rules:

- Feeds DLQ/operator dashboard.
- Does not silently mutate source business rows.
