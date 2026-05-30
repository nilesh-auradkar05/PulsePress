# PulsePress Test Plan

**Version:** v1.1  
**Scope:** Phase 1  
**Canonical for:** concrete tests. Tests verify behavior, not implementation internals.

## 1. Test philosophy

The oracle is the contract:

- API behavior: `docs/openapi.yaml`
- Events: `docs/event-catalog.md`
- State transitions: `docs/architecture.md`
- Data invariants: migrations and DB constraints

Forbidden:

- Mocking internal service methods to prove behavior.
- Asserting private attributes.
- Asserting internal call order.
- Testing implementation structure instead of observable behavior.

Allowed:

- Public API calls.
- Direct DB assertions after public actions.
- Documented fixture builders under `tests/fixtures` or `tests/factories`.
- Event handler tests that feed catalog-valid events and assert DB/S3/Redis side effects.

## 2. API tests

### Auth

| Case | Expected |
|---|---|
| Missing token on protected route | 401 Problem |
| Invalid token | 401 Problem |
| Expired token | 401 Problem |
| Valid token on `/me` | 200 User |
| Local dev shortcut outside local env | 404/disabled |

### Publications

| Case | Expected |
|---|---|
| Create publication | 201 Publication |
| Duplicate handle | 409 Problem |
| Invalid handle | 422 Problem |
| Get publication | 200 PublicationDetail |
| Update owner profile fields | 200 Publication |
| Non-owner update | 403 Problem |
| Publication update emits event | Must not happen |

### Plans

| Case | Expected |
|---|---|
| Owner creates free plan | 201 Plan |
| Owner creates paid plan | 201 Plan |
| Non-owner creates plan | 403 |
| Negative price | 422 |
| Non-USD currency | 422 |
| Open amount above floor accepted during subscribe | 201 SubscriptionResult |
| Amount below floor rejected | 422 |

### Posts

| Case | Expected |
|---|---|
| Owner creates draft | 201 Post |
| Non-owner creates post | 403 |
| Edit draft | 200 Post |
| Edit published post | 200 Post, no event |
| Archive post | 200 archived |
| Archive already archived | 200 no-op |
| Publish draft | 200 queued + snapshot + outbox |
| Publish already published | 200 already_processed, no duplicate outbox |
| Publish archived | 422 |
| Non-subscriber gets paid post | 200 metadata, `body=null`, `entitled=false` |
| Paid subscriber gets paid post | 200 with body |

### Subscriptions

| Case | Expected |
|---|---|
| Free subscribe | 201, bill null, outbox event, no ledger |
| Paid subscribe | 201, bill, outbox event, no ledger before worker |
| Self-subscribe | 403 |
| Duplicate active subscription | 409 unless idempotency replay |
| Missing idempotency key | 422/400 Problem |
| Same key + same body | replay original with `Idempotency-Replayed: true` |
| Same key + different body | 422 idempotency-conflict |
| Change tier | 200, outbox event, no ledger |
| Cancel active | 200 canceled, access retained |
| Cancel already canceled | 200 no-op, no duplicate event |

### Gifts

| Case | Expected |
|---|---|
| Send gift | 201 pending + bill + outbox |
| Self-gift | 403 |
| Amount below 50 cents | 422 |
| Missing idempotency key | 422/400 |
| Same key replay | original response |
| Same key different body | 422 |

### Feed/SSE

| Case | Expected |
|---|---|
| Publication events owner | sees full event stream |
| Publication events subscriber | sees public-safe subset |
| User feed events | sees own feed only |
| Cross-user feed access | impossible/not exposed |
| SSE event format | `data:` JSON matching schema |

### Admin

| Case | Expected |
|---|---|
| Non-admin list outbox | 403 |
| Admin list outbox | 200 |
| Retry failed event | 200 + reconciliation_log |
| Retry missing idempotency | error |
| Amend flag off | 403 |
| Amend bad signature | 422 |
| Amend good signature with flag on | new outbox + original superseded |
| Discard short reason | 422 |
| Discard valid | discarded + reconciliation review |

## 3. Worker tests

| Handler | Case | Expected |
|---|---|---|
| outbox poller | two pollers | no double-claim |
| outbox poller | EventBridge failure | row remains retryable |
| idempotency | same event twice | one durable effect |
| subscription.created | free | stats/feed only, no ledger |
| subscription.created | paid | 1 ledger transaction + 3 entries + receipt |
| gift.sent | valid | 1 ledger transaction + 3 entries + receipt |
| post.published | valid | newsletter requested |
| newsletter.send.requested | free post | all active subscribers |
| newsletter.send.requested | paid post | paid active + canceled-with-access only |
| newsletter.send.requested | S3 failure | newsletter failed event/status |
| Redis publish | Redis down | DB success, live stream degraded |
| invalid event version | unsupported | failure recorded, no mutation |

## 4. Invariant/property tests

- Ledger transaction CHECK rejects unbalanced values.
- Every paid source has exactly one `ledger_transactions` row.
- Every ledger transaction has exactly one author, platform, and tax entry.
- `sum(ledger_entries.amount_cents) == ledger_transactions.total_charged_cents`.
- No float usage in money module.
- API outbox atomicity: no business row without expected outbox event.
- Worker duplicate delivery does not duplicate ledger/read model rows.
- `post_versions` immutable after publish.
- `ledger_transactions` and `ledger_entries` immutable.
- Redis loss does not change DB truth.
- Request correlation ID appears in response, logs, and event envelope.

## 5. Frontend tests

- Login state renders correctly.
- Publication create form validates handle/name.
- Post editor supports draft/publish/archive states.
- Paid post gated state is screenshot-readable.
- Subscribe form shows bill breakdown before/after submit.
- Idempotency replay does not duplicate success UI.
- Writer dashboard handles loading/empty/success/error.
- SSE reconnect preserves durable event list.
- Admin runbook forms require reason and confirmation.

Verification:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web test
pnpm --dir apps/web build
pnpm --dir apps/web exec playwright test
```

## 6. Infra tests

- `terraform fmt -check`.
- `terraform validate`.
- `terraform plan` when credentials are configured.
- RDS public accessibility is false.
- ElastiCache public accessibility is false/private subnet only.
- S3 public access block enabled.
- IAM policies scoped to required resources.
- No secrets in Terraform defaults or Git history.
- Required tags present on every resource.
- `terraform apply/destroy` blocked unless explicitly approved.

## 7. Acceptance test

The deployed MVP passes when:

1. User A logs in.
2. User A creates publication and plans.
3. User A drafts and publishes a post.
4. Worker stores newsletter artifact and feed events.
5. User B subscribes to paid tier using idempotency key.
6. API returns transparent bill.
7. Worker writes one ledger transaction plus three entries.
8. Redis invalidates summary/dashboard stream updates.
9. Admin recovers a deliberately failed event.
10. CloudWatch trace and alarm evidence are captured.
11. GitHub Actions build/test/deploy is green.
