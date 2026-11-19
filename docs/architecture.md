# PulsePress Architecture

**Version:** v1.1  
**Scope:** Phase 1 only  
**Purpose:** Separate architecture decisions from execution tasks and AI-agent rules.

## 1. Architecture goal

PulsePress is a cloud-deployed, Substack-style publishing and subscription platform. The architecture must demonstrate production-shaped backend engineering without accidentally turning into a fake payments company, because apparently that is how portfolio projects become legal discovery exhibits.

The system proves:

- FastAPI service design with Cognito auth.
- PostgreSQL domain modeling with Alembic migrations.
- Redis cache/fanout without Redis becoming source of truth.
- Transactional outbox with EventBridge/SQS async processing.
- Idempotent workers, DLQ handling, and operator recovery.
- Ledger transaction modeling using integer cents.
- Terraform-deployed AWS infrastructure.
- OpenTelemetry/CloudWatch observability.

## 2. Canonical artifacts

| Concern | Canonical artifact |
|---|---|
| Product scope/prose decisions | `docs/SPEC.md` |
| HTTP API | `docs/openapi.yaml` |
| Event payloads | `docs/event-catalog.md` |
| Architecture/design | `docs/architecture.md` |
| Execution tasks | `docs/sprint-plan.md` |
| Verification/test matrix | `docs/test-plan.md` |
| Claude Code behavior | `CLAUDE.md` |
| Claude-specific behavior | `CLAUDE.md` |

## 3. Central architecture rule: two write-shapes

### Commerce writes are money-shaped

Includes:

- Subscribe.
- Change tier.
- Cancel subscription.
- Send gift.
- Admin retry/amend/discard.

They must:

- Require `Idempotency-Key`.
- Validate through OpenAPI-generated schemas.
- Write business row + idempotency record + outbox event in the same PostgreSQL transaction when an event is emitted.
- Produce ledger data only through the worker.
- Be safe under duplicate client requests and duplicate SQS deliveries.

### Publishing writes are content-shaped

Includes:

- Create publication.
- Update publication profile.
- Create/edit/archive post.
- Create/list plans, except subscription mutations are commerce.

They must:

- Use normal authenticated CRUD.
- Not require idempotency keys.
- Not write outbox events.
- Not touch ledger tables.

### The only publishing event-door

`publishPost` is the one exception:

- `draft → published` writes an immutable `post_versions` snapshot.
- It writes `post.published` to the outbox in the same DB transaction.
- Worker renders newsletter and fanout from the snapshot, not the mutable post body.

## 4. Runtime services

### API service

Responsibilities:

- Validate Cognito JWTs.
- Own transactional writes.
- Enforce request idempotency for commerce endpoints.
- Compute bill breakdown once using integer cents and round-half-up.
- Write outbox rows in the same transaction as source business rows.
- Serve query/read endpoints and SSE streams.
- Propagate `correlation_id` into logs, responses, and event envelopes.

Forbidden:

- Business logic in route handlers.
- AWS SDK calls from route handlers.
- Ledger writes in API handlers.
- Floating-point money math.

### Worker service

Responsibilities:

- Run the outbox poller.
- Publish outbox events to EventBridge.
- Consume SQS messages.
- Deduplicate by `event_id`.
- Write ledger transactions and ledger entries.
- Render receipt/newsletter artifacts to S3.
- Update read models and Redis notifications.
- Record worker attempts and surface failures.

### Outbox poller

Pattern:

```text
SELECT pending outbox rows FOR UPDATE SKIP LOCKED
publish to EventBridge
mark published
```

This is publish-then-mark, so delivery is at-least-once. Worker idempotency is mandatory.

## 5. Data model

Phase 1 uses 17 tables.

### Identity

- `users`

### Publishing

- `publications`
- `posts`
- `post_versions`
- `newsletter_sends`

### Commerce

- `subscription_plans`
- `subscriptions`
- `gift_transactions`
- `ledger_transactions`
- `ledger_entries`

### Reliability kernel

- `outbox_events`
- `idempotency_keys`
- `event_processing_attempts`

### Read models

- `publication_daily_stats`
- `user_feed_events`
- `notification_events`

### Operability

- `reconciliation_log`

## 6. Ledger model

Do **not** enforce cross-row balance with a PostgreSQL `CHECK` on `ledger_entries`. PostgreSQL row-level CHECK constraints cannot sum sibling rows. Architecture documents may dream; databases, annoyingly, operate.

Use:

```text
ledger_transactions
- principal_amount_cents
- author_net_cents
- platform_fee_cents
- tax_cents
- total_charged_cents
CHECK(author_net_cents + platform_fee_cents + tax_cents = total_charged_cents)
CHECK(principal_amount_cents + tax_cents = total_charged_cents)
UNIQUE(source_type, source_id)
```

Then materialize:

```text
ledger_entries
- ledger_transaction_id
- account: author | platform | tax
- amount_cents
UNIQUE(ledger_transaction_id, account)
```

Worker writes `ledger_transactions` plus exactly three `ledger_entries` in one DB transaction.

## 7. Money rules

- Currency is `USD` only.
- Money is integer cents only.
- Use round-half-up for `tax` and `platform_fee`.
- `author_net = principal_amount_cents - platform_fee_cents`.
- `total_charged = principal_amount_cents + tax_cents`.
- Worker does not rederive bill splits; it trusts the event payload and validates invariants before writing.

## 8. Event backbone

```text
API transaction
  → outbox_events
  → outbox poller
  → EventBridge
  → SQS
  → worker handler
  → ledger/read models/S3/Redis
  → SSE/dashboard/feed
```

## 9. Phase-1 events

Publishing:

- `post.published`
- `newsletter.send.requested`
- `newsletter.sent`
- `newsletter.send.failed`

Commerce:

- `subscription.created`
- `subscription.tier_changed`
- `subscription.canceled`
- `gift.sent`

Kernel:

- `ledger.transaction.recorded`
- `event.processing.failed`

## 10. Newsletter and feed fanout

Recipient rules:

- Free posts fan out to all active subscribers.
- Paid posts fan out to active paid subscribers only.
- Canceled subscriptions retain paid access until `access_until` or `period_end`.
- Expired subscriptions are excluded.
- Recipient user IDs are snapshotted while handling `post.published`.
- Owner is excluded because self-subscribe is forbidden.

Durable reader notifications are written to `user_feed_events`. Publication dashboard events are written to `notification_events`.

## 11. Admin operability

Admin verbs:

1. `retry` — safe, resets failed/superseded event to pending when allowed.
2. `amend & retry` — feature-flagged off by default, creates a new event and supersedes old one.
3. `discard` — terminal, opens reconciliation review.

Every admin action writes `reconciliation_log` with before/after state.

For Phase 1, `admin_signature` is typed confirmation: `AMEND <event_id>`. It is not a cryptographic HMAC.

## 12. Cloud architecture

AWS resources:

- ALB → ECS Fargate API.
- ECS Fargate worker.
- RDS PostgreSQL.
- ElastiCache Redis.
- EventBridge bus.
- SQS queue + DLQ.
- S3 private buckets.
- Cognito user pool/client.
- CloudWatch logs, metrics, alarms.
- ADOT/OpenTelemetry collector path.

Security constraints:

- RDS and ElastiCache are private.
- S3 buckets are private.
- IAM is least privilege.
- No static AWS credentials in code or Terraform.
- `terraform apply/destroy` only after explicit user approval.

## 13. Architectural non-goals

Phase 1 explicitly excludes:

- Stripe or real payments.
- Refunds, payouts, proration, recurring billing.
- Real email.
- Claps, comments, bookmarks, follows.
- Search, tags, trending, recommendations, home-discovery feed.
- Publication roles/workflow.
- Kubernetes.
- Multi-region.
