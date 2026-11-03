# PulsePress Test Plan

**Version:** v1.2 (architecture revision v1.2; supersedes v1.1)
**Scope:** Phase 1
**Canonical for:** concrete tests, test families, and the per-sprint verification matrix. Tests verify behavior, not implementation internals.

## 1. Test philosophy

The oracle is the contract:

- API behavior: `docs/openapi.yaml`
- Events: `docs/event-catalog.md`
- State transitions: `docs/architecture.md` (and `docs/architecture-revision.md` until folded in)
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
- Injected adapters at the integration boundary (in-memory receipt store, local publisher, fake CloudWatch client) when the adapter is the unit under contract, never to stub business logic.

### 1.1 Test families

Every sprint from Sprint 5 on ships evidence for each family its feature touches. The first five
are mandatory in every sprint.

| Family | Question it answers | Scope | Tooling | How it is selected |
|---|---|---|---|---|
| Unit | Is the pure logic right? | Functions and small classes with no I/O: money math, envelope parsing, recipient predicate, PKCE helpers, cursor codecs, eligibility matrices | pytest, Vitest | `@pytest.mark.unit`; `apps/web/**/*.test.ts` |
| Integration | Does the component behave against real dependencies? | API routes over a real PostgreSQL; worker handlers over a migrated schema with in-memory S3/EventBridge adapters; Redis container where the feature needs it | pytest with `TEST_DATABASE_URL` (and `TEST_REDIS_URL`) | `@pytest.mark.integration` (`and redis` for Redis-backed) |
| Contract | Does the surface match the published contract? | HTTP responses vs OpenAPI; event payloads vs catalog; generated schemas vs `docs/openapi.yaml`; migrations vs models | `scripts/ci/validate_openapi.py`, schema-generation drift check, `alembic check`, payload validators | `@pytest.mark.contract` and CI scripts |
| Regression | Did anything that used to work break? | All previous sprints' suites; one named test per fixed bug (`test_regression_<topic>`) | full pytest run of api and worker | `@pytest.mark.regression` plus the full run |
| End-to-end smoke | Does the feature work through the running stack? | `scripts/integration/acceptance_local.sh --through sprint-N` against docker compose; AWS smoke per the production guide | shell + curl + psql | manual or CI nightly |
| Infra | Is the infrastructure valid and policy-safe? | Terraform fmt/validate/plan; policy scripts (tags, no HTTP-only listener after Sprint 8, alarm count) | terraform, `scripts/ci/*.py` | CI terraform job |
| Load | Do latency and throughput targets hold? | k6 scenarios with thresholds | k6 | Sprint 12, then any sprint touching a hot path |
| Chaos | Do documented failure modes recover? | `scripts/chaos/*` against the local stack or AWS | shell | Sprint 11 onward |

### 1.2 Markers and commands

Markers are registered in `apps/api/pyproject.toml` and `apps/worker/pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
  "unit: pure logic, no I/O",
  "integration: needs TEST_DATABASE_URL (and TEST_REDIS_URL when tagged redis)",
  "redis: needs a Redis instance",
  "contract: validates against OpenAPI / event catalog / migrations",
  "regression: guards a previously fixed bug",
]
```

```bash
cd apps/api
uv run pytest -m unit
uv run pytest -m "integration and not redis"
uv run pytest -m contract
uv run pytest                       # everything; this is what CI runs
```

Database-backed tests skip when `TEST_DATABASE_URL` is unset locally. **CI never skips them:**
both the `api` and `worker` jobs provide a Postgres service (Sprint 5), and Redis is added to the
`api` job in Sprint 7.

### 1.3 CI matrix

| Job | Steps |
|---|---|
| api | `uv sync`, `ruff check`, `pyright`, `alembic check`, `alembic heads` (one head), `pytest` with Postgres (+ Redis from Sprint 7) |
| worker | `uv sync`, `ruff check`, `pyright`, `pytest` with Postgres |
| web | `pnpm install --frozen-lockfile`, `lint`, `typecheck`, `test` (Vitest), `build`, Playwright from Sprint 7 |
| terraform | `fmt -check -recursive`, `init -backend=false`, `validate`, policy scripts |
| guardrails | `validate_openapi.py`, `check_docs_links.py docs CLAUDE.md README.md` (full docs tree), `test_agent_hooks.py` |
| nightly (from Sprint 7) | `acceptance_local.sh` on a fresh clone; k6 smoke from Sprint 12 |

A red job blocks merge. A skipped database suite is treated as red.

## 2. API tests

### Auth

| Case | Family | Expected |
|---|---|---|
| Missing token on protected route | integration | 401 Problem with `correlation_id` |
| Invalid token | integration | 401 Problem |
| Expired token | unit (verifier) | 401 Problem |
| Bad issuer / audience / token_use | unit (verifier) | 401 Problem |
| Valid token on `/me` | integration | 200 User |
| Local dev shortcut outside local env | contract | router absent (404) |
| Browser PKCE: verifier/challenge, `state` check, token storage (Sprint 8) | unit (Vitest) | S256 challenge matches; mismatched `state` rejected |

### Publications

| Case | Family | Expected |
|---|---|---|
| Create publication | integration | 201 Publication |
| Duplicate handle | integration | 409 Problem |
| Invalid handle | contract | 422 Problem |
| Get publication detail with plans | integration | 200 PublicationDetail with active plans |
| Get publication summary | integration | 200 counts; excludes expired subscriptions (Sprint 7); revenue from ledger (Sprint 7) |
| Summary served from Redis cache and invalidated after a commerce commit (Sprint 7) | integration (redis) | second read is a cache hit; post-commit read reflects the change |
| Update owner profile fields | integration | 200 Publication |
| Non-owner update | integration | 403 Problem |
| Publication update emits event | regression | must not happen |

### Plans

| Case | Family | Expected |
|---|---|---|
| Owner creates free plan | integration | 201 Plan |
| Owner creates paid plan | integration | 201 Plan |
| Non-owner creates plan | integration | 403 |
| Negative price | contract | 422 |
| Non-USD currency | contract | 422 |
| Open amount above floor accepted during subscribe | integration | 201 SubscriptionResult |
| Amount below floor rejected | integration | 422 |

### Posts

| Case | Family | Expected |
|---|---|---|
| Owner creates draft | integration | 201 Post |
| Non-owner creates post | integration | 403 |
| Edit draft / edit published post | integration | 200 Post, no event |
| Archive post / archive already archived | integration | 200 archived / 200 no-op |
| Publish draft | integration | 200 queued + snapshot + outbox |
| Publish already published | regression | 200 already_processed, no duplicate outbox |
| Publish archived | integration | 422 |
| Non-subscriber / free subscriber gets paid post | integration | 200 metadata, `body=null`, `entitled=false` |
| Paid subscriber / canceled paid subscriber before `access_until` | integration | 200 with body |
| Publishing service extraction keeps responses identical (Sprint 6) | contract | recorded responses for the walkthrough payloads match byte for byte |

### Subscriptions

| Case | Family | Expected |
|---|---|---|
| Free subscribe | integration | 201, bill null, outbox event, no ledger |
| Paid subscribe | integration | 201, bill, outbox event, no ledger before worker |
| Self-subscribe | integration | 403 |
| Duplicate active subscription | integration | 409 unless idempotency replay |
| Missing idempotency key | contract | 422 Problem |
| Same key + same body | integration | replay original with `Idempotency-Replayed: true` |
| Same key + different body | integration | 422 idempotency-conflict |
| Concurrent same-key subscribe | integration | one subscription/outbox row, one replay |
| Concurrent duplicate active subscribe with different keys | regression | one 201 and one 409 |
| Stale in-flight claim | integration | 409 idempotency-in-flight until `locked_until` expires |
| Change tier | integration | 200, outbox event, no ledger |
| Cancel active / cancel already canceled | integration | 200 canceled, access retained / 200 no-op, no duplicate event |

### Gifts

| Case | Family | Expected |
|---|---|---|
| Send gift | integration | 201 pending + bill + outbox |
| Self-gift | integration | 403 |
| Amount below 50 cents | contract | 422 |
| Missing idempotency key | contract | 422 |
| Same key replay / same key different body | integration | original response / 422 |
| Concurrent same-key gift | integration | one gift/outbox row, one replay |

### Feed and SSE (Sprint 7)

| Case | Family | Expected |
|---|---|---|
| Publication events: owner | integration | full event stream |
| Publication events: subscriber | integration | public-safe subset |
| User feed events | integration | own feed only |
| Cross-user feed access | integration | not exposed |
| SSE event format | contract | `data:` JSON matching schema; `: keepalive` every 15 s |
| Reconnect with cursor | integration | replay from durable rows, no duplicates |
| Redis unavailable | integration (redis) | stream stays open, `degraded` comment, polling fallback; DB unchanged |
| Pagination | contract | `cursor` + `limit` (max 100, default 25) |
| 100 concurrent SSE clients for five minutes | load smoke | no errors, memory flat |

### Admin (Sprints 9–10)

| Case | Family | Expected |
|---|---|---|
| Non-admin list outbox / attempts / reconciliations | integration | 403 |
| Admin list with status filters and pagination | integration | 200 |
| Retry publish-failed row | integration | outbox back to pending, `terminal_at` cleared, audit row |
| Retry handler-failed event | integration | attempt `terminal_at` cleared, `attempt_number` 0, outbox pending, no second failure event, audit row |
| Retry succeeded / discarded / superseded | unit + integration | rejected per eligibility matrix |
| Retry missing idempotency key or reason | contract | 422 |
| Retry same key replay | integration | stored response |
| Amend flag off | integration | 403 |
| Amend bad signature | contract | 422 |
| Amend good signature with flag on | integration | new outbox row with causation, original superseded, audit row |
| Discard short reason | contract | 422 |
| Discard valid | integration | discarded + reconciliation review opened |
| DLQ depths visible (metric or metadata) | integration | both queues reported |

## 3. Worker tests

| Handler | Case | Family | Expected |
|---|---|---|---|
| outbox poller | two pollers | integration | no double-claim (`SKIP LOCKED`) |
| outbox poller | EventBridge failure | integration | row retryable with exponential backoff |
| outbox poller | retry exhaustion | integration | terminal `failed`, not silently discarded |
| outbox poller | all ten catalog types (Sprint 6) | contract | every type publishes; unknown type is terminal after five attempts |
| idempotency | same event twice | integration | one durable effect |
| idempotency | concurrent delivery during a live lease | integration | `EventInProgressError`, message left for SQS |
| idempotency | reclaim after lease expiry | integration | attempt number increments; no duplicate durable effect |
| subscription.created | free | integration | stats and notification row only, no ledger |
| subscription.created | paid | integration | validates creation snapshot; 1 ledger transaction + 3 entries + receipt |
| gift.sent | valid | integration | validates source; 1 ledger transaction + 3 entries + receipt; gift processed |
| subscription.tier_changed / canceled (Sprint 7) | integration | one notification row; cancel writes a `-1` daily delta |
| receipt store | same receipt write | unit + integration | idempotent; conflicting content rejected |
| source conflict | conflicting event | integration | no receipt or additional ledger mutation |
| poison delivery | final receive | integration | one failure event; message remains for SQS redrive |
| receive-count inflation | lease contention | regression | never terminal from SQS receive count |
| post.published (Sprint 6) | valid, twice | integration | one `newsletter_sends` row, one `newsletter.send.requested` |
| newsletter.send.requested | free post | integration | all active subscribers; owner excluded |
| newsletter.send.requested | paid post | integration | paid active + canceled-with-access only; expired excluded |
| newsletter.send.requested | recipient predicate | unit | fixture matrix of status × `access_until` × amount |
| newsletter.send.requested | post edited after publish | integration | artifact renders from `post_versions`, unchanged |
| newsletter.send.requested | duplicate delivery | integration | no new `user_feed_events` (unique on user, source_event_id) |
| newsletter.send.requested | crash after artifact PUT | integration | reclaim completes; artifact idempotent; counts unchanged |
| newsletter.send.requested | S3 failure | integration | retryable; terminal → `failed` + `newsletter.send.failed` |
| Redis publish (Sprint 7) | Redis down | integration (redis) | DB commit succeeds, publish failure logged |
| worker roles (Sprint 11) | poller-only / consumer-only | integration | each role runs alone; idle consumer does not delay the poller |
| metrics (Sprint 11) | one cycle | integration | fake CloudWatch client receives the seven metric names |
| invalid event version | unsupported | integration | failure recorded, no mutation |

## 4. Invariant and property tests

- Ledger transaction CHECK rejects unbalanced values.
- Every paid source has exactly one `ledger_transactions` row.
- Every ledger transaction has exactly one author, platform, and tax entry; the deferred trigger rejects incomplete, duplicate-account, cross-publication, or unbalanced sets at commit.
- `sum(ledger_entries.amount_cents) == ledger_transactions.total_charged_cents`.
- Subscription creation-time charge facts remain stable after a tier change; migration backfill uses the original `subscription.created` event when present.
- No float usage in money modules (API and worker).
- API outbox atomicity: no business row without its outbox event.
- Worker duplicate delivery does not duplicate ledger, feed, notification, or stats rows.
- `newsletter_sends` has at most one row per post; `user_feed_events` at most one per `(user_id, source_event_id)`; `notification_events` at most one per `(publication_id, source_event_id, event_type)`.
- `publication_daily_stats` totals equal the sums of daily deltas; a cancel contributes `-1`.
- `post_versions`, `ledger_transactions`, `ledger_entries`, `reconciliation_log` are immutable.
- Redis loss does not change DB truth.
- Request correlation ID appears in response, logs, and event envelope; worker events carry `causation_id`.
- `alembic check` is empty against head; exactly one head exists.
- `Base.metadata` in `pulsepress_schema` lists exactly 17 tables and no app defines a model of its own.

## 5. Frontend tests

Unit (Vitest):

- API client sets `Idempotency-Key` on every commerce write and never on publishing writes.
- PKCE helpers and `state` verification (Sprint 8).
- SSE hook: cursor persistence and reconnect (Sprint 7).
- Admin forms: reason length and `AMEND <event_id>` confirmation (Sprints 9–10).

End-to-end (Playwright):

- Login state renders; local mode and production mode switch by `NEXT_PUBLIC_AUTH_MODE`.
- Publication create form validates handle/name.
- Post editor supports draft/publish/archive states.
- Paid post gated state is screenshot-readable.
- Subscribe form shows bill breakdown before/after submit; idempotency replay does not duplicate success UI.
- Author plan creation UI creates and lists plans.
- Reader post view subscribes to a paid plan and unlocks the body; sends a gift and displays total charged.
- Unsupported destructive actions render disabled.
- Writer dashboard handles loading/empty/success/error and updates live after a subscribe in another context (Sprint 7).
- SSE reconnect preserves the durable event list.
- Admin runbook: retry, amend, discard flows (Sprints 9–10).
- Production build does not require a live Google Fonts fetch.

Verification:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web test
pnpm --dir apps/web build
pnpm --dir apps/web exec playwright test
```

## 6. Infra tests

- `terraform fmt -check -recursive`, `init -backend=false`, `validate`; `plan` when credentials are configured.
- RDS `publicly_accessible = false`; ElastiCache in private subnets.
- S3 artifact bucket: public access block, versioning, SSE, TLS-only policy.
- Worker task role: `events:PutEvents` on the bus, consume/delete on the worker queue only, `s3:PutObject`/`GetObject` under `receipts/*` and `newsletters/*` only (Sprint 6).
- EventBridge rule lists all ten detail-types (Sprint 6).
- HTTPS listener exists and HTTP redirects (Sprint 8); policy script fails on an HTTP-only product listener.
- Exactly five named alarms; seven metric names referenced (Sprint 11).
- `visibility_timeout_seconds > event_lock_seconds + handler budget` asserted by a variable validation block (Sprint 11).
- Required tags present on every resource (`scripts/ci/check_cost_tags.py`).
- No secrets in Terraform defaults or Git history.
- `terraform apply/destroy` blocked unless explicitly approved.

## 7. Load tests (Sprint 12, then on hot-path changes)

Scenarios in `scripts/load/phase1_acceptance.js`:

| Scenario | Load | Threshold |
|---|---|---|
| Read publication / post | 100 req/s for 5 min | p95 < 300 ms, error rate < 0.1% |
| Paid subscribe with fresh keys | 20 req/s for 5 min | p95 < 500 ms; exactly one subscription per key |
| Gift | 20 req/s for 5 min | p95 < 500 ms |
| Publish to 10k subscribers | 1 publish | fanout complete < 30 s; `user_feed_events` count = recipients |
| Outbox to handler latency | measured during the above | p95 < 5 s |
| SSE | 100 connections for 5 min | no disconnects, memory flat |

Every k6 run asserts data integrity afterwards: no duplicate ledger transactions, balanced entries, no orphaned outbox rows.

## 8. Chaos tests (Sprint 11 onward)

| Script | Injects | Expected |
|---|---|---|
| `scripts/chaos/poison_event.sh` | an outbox row with an invalid payload | terminal after five attempts, one `event.processing.failed`, DLQ depth 1, alarm fires, admin retry recovers after the payload is amended |
| `scripts/chaos/break_worker.sh` | stops the worker for N minutes | outbox age alarm fires; queue buffers; restart drains with no duplicates |
| manual | stop Redis | SSE degrades, DB truth unchanged |
| manual | deny S3 PUT | newsletter retryable then `failed`; ledger receipt path retryable |

## 9. Regression policy

- Every bug fixed after Sprint 4 gets a named test `test_regression_<topic>` with a one-line docstring linking the lesson or issue.
- Previous sprints' suites run on every push; a sprint cannot close with a skipped or removed test.
- Behaviour changes that alter a recorded response require updating the contract fixtures in the same change, with the diff explained in `tasks/todo.md`.
- `scripts/integration/acceptance_local.sh` grows one `--through sprint-N` stage per sprint and is the regression gate for end-to-end behaviour.

## 10. Per-sprint verification matrix

| Sprint | Feature | Unit | Integration | Contract | Regression | E2E smoke | Infra | Load | Chaos |
|---|---|---|---|---|---|---|---|---|---|
| 5 | Shared schema package + migration integrity | package import, 17 tables | migration roundtrip; worker on migrated schema | `alembic check`, one head, docs links | full suites on fresh clone | acceptance through Sprint 4 | CI jobs | — | — |
| 6 | Newsletter fanout | recipient predicate, dispatch table | handlers, idempotency, crash reclaim, S3 failure | event payloads, response byte-equality | Sprint 3–4 suites | publish → artifact + feed | IAM prefixes, rule entries | — | — |
| 7 | Live dashboard + feed | cursor codec, stats deltas | SSE, Redis down, read models | OpenAPI feed schemas, SSE shape | prior suites | subscribe → dashboard update | — | 100 SSE clients | — |
| 8 | TLS + Cognito PKCE | PKCE helpers | JWT verifier fixtures | local router absent in prod | Sprint 2 auth suite | hosted-UI login in AWS | listener 443, redirect, callback URLs | — | — |
| 9 | Admin inspection + retry | eligibility matrix | two-locus retry, audit rows | admin schemas, 403/422 | worker idempotency | poison → retry → success | — | — | poison script |
| 10 | Amend + discard + reconciliation | signature parser | amend/discard flows, immutability | catalog-valid amended payload | retry eligibility | admin UI forms | — | — | — |
| 11 | Observability + worker roles | formatter, metric emitter | role isolation, trace spans | — | Sprint-4 worker suite | alarm fires in AWS | alarm count, tags, visibility invariant | — | both scripts |
| 12 | Hardening + load | — | archival invariants | — | full suites | rebuild from zero | empty plan after rebuild | all scenarios | evidence pack |
| 13 | Portfolio polish | — | — | docs links | full suites | fresh-clone script | — | — | — |

## 11. Acceptance test

The deployed MVP passes when:

1. User A logs in through Cognito over HTTPS.
2. User A creates a publication and plans.
3. User A drafts and publishes a post.
4. The worker stores the newsletter artifact and feed events and emits `newsletter.sent`.
5. User B subscribes to a paid tier using an idempotency key.
6. The API returns the transparent bill.
7. The worker writes one ledger transaction plus three entries and a receipt.
8. Redis invalidates the summary; the dashboard updates over SSE.
9. An admin recovers a deliberately failed event with an audited retry.
10. CloudWatch trace and alarm evidence are captured.
11. GitHub Actions build/test is green and the k6 report meets thresholds.
