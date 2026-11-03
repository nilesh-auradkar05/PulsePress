# PulsePress — Project Specification

**Spec version:** v1.4 (architecture revision v1.2 and one-feature sprints; supersedes v1.3)
**Product:** Event-driven creator publishing & subscription platform (Substack-model)
**Purpose:** SWE/SDE portfolio project
**Development model:** Spec-driven, Claude Code–assisted, deployed on AWS
**Primary goal:** Build a concise, cloud-deployed, production-shaped publishing-and-subscription platform where writers publish posts and earn through paid subscriptions and gifts, processed through an event-driven backend with full operability — then extend with Medium-style engagement and discovery features in Phase 2.

**What v1.4 changes.** The worker processing contract observed in Sprint 4 becomes canonical (§11); the schema gains additive idempotency constraints for fanout and read models (§6); all ten events are routed from Sprint 6 (§8); daily statistics are defined as deltas (§6.5); admin `retry` is specified for both failure loci (§12); seven operability metrics replace six (§12); TLS is required before the browser login flow (§14); one SQLAlchemy model set and one Alembic chain live in a shared package, and migrations and this spec pack are tracked in git (§15); the remaining work is re-cut into single-feature sprints that each ship the full test-family set (§16); ADRs 0013–0015 are added (§17).

---

## 0. How to read this spec

This document is the authoritative text specification. It is accompanied by paired AI-readable Markdown companions and portfolio-ready HTML diagrams under `docs/design-md/` and `docs/design/`. Markdown companions are the canonical design summaries for coding agents; HTML diagrams are visual companions for humans, screenshots, and the README. The OpenAPI file (`docs/openapi.yaml`) is canonical for the HTTP contract.

**Every file named here is tracked in git.** The spec pack, ADRs and Alembic migrations are not ignored, so CI, fresh clones and cloud sessions see the same truth as the author's machine (ADR-0015).

| Artifact | Markdown companion | HTML visual | Shows |
| --- | --- | --- | --- |
| High-Level Architecture | `docs/design-md/pulsepress-hld-architecture.md` | `docs/design/pulsepress-hld-architecture.html` | System context, AWS boundary, event backbone |
| Component / Bounded Contexts | `docs/design-md/pulsepress-component-context.md` | `docs/design/pulsepress-component-context.html` | Two write-contexts + shared backbone |
| ER / Domain Model | `docs/design-md/pulsepress-er-model.md` | `docs/design/pulsepress-er-model.html` | 17 Phase-1 tables, FK clusters, invariants |
| State Machines | `docs/design-md/pulsepress-state-machines.md` | `docs/design/pulsepress-state-machines.html` | Post, subscription, gift lifecycles |
| Paid Subscribe Sequence | `docs/design-md/pulsepress-seq-subscribe.md` | `docs/design/pulsepress-seq-subscribe.html` | Money-shaped flow end-to-end |
| Publish → Newsletter Sequence | `docs/design-md/pulsepress-seq-publish.md` | `docs/design/pulsepress-seq-publish.html` | Content-shaped flow with the event-door |
| Operability Layer | `docs/design-md/pulsepress-operability.md` | `docs/design/pulsepress-operability.html` | Detection, action, reconciliation |
| Subscription Bill Breakdown | `docs/design-md/pulsepress-bill-breakdown.md` | `docs/design/pulsepress-bill-breakdown.html` | The three-way money split |
| Subscription Tiers | `docs/design-md/pulsepress-subscription-tiers.md` | `docs/design/pulsepress-subscription-tiers.html` | Multi-tier pricing model |
| Event Catalog Summary | `docs/event-catalog.md` | `docs/design/pulsepress-event-catalog.html` | 10 events, payload summary, renamed ledger event |
| API Contract Summary | `docs/openapi.yaml` | `docs/design/pulsepress-api-contract.html` | 21 path entries, 29 operations, 32 schemas |
| Sprint Plan Summary | `docs/sprint-plan.md` | `docs/design/pulsepress-sprint-plan.html` | Sprint goals, task traces, verification gates |
| Architecture Revision v1.2 | `docs/architecture-revision.md` | Archify set under `.archify/` (moved to `docs/design/` in Sprint 13) | As-built vs designed delta, worker contract, Sprint 5–13 LLD |

---

## 1. Product Strategy

### 1.1 Identity

PulsePress is **publication-centric** (the Substack model), not platform-centric (the Medium model). This is a structural consequence of the monetization decision: **authors set their own subscription prices, and the platform takes a cut of each specific payment.** That only makes sense when readers pay a publication directly — which is the Substack shape. A platform-wide membership pool (Medium) is incompatible with author-set per-publication pricing and is explicitly not the model here.

### 1.2 Build order — two phases

**Phase 1 (this spec) — deployed MVP.** Writer publications, post drafting/publishing, free and paid subscriptions (multi-tier), one-time gifts, newsletter-send simulation, a three-way money split with transparent billing, an event-driven backend, a real-time dashboard, a full operability layer, and cloud deployment with Terraform.

**Phase 2 — Medium-style expansion (deferred).** Reader engagement (claps, bookmarks, comments), discovery (tags, topic pages, trending, home feed, search), publication member roles, read-time analytics. Phase 2 must not begin until Phase 1 is deployed, verified, load-tested, and documented (see §18.2 entry criteria).

**Phase 3 — real money (future).** Stripe integration, real payouts, refunds, and the saga/compensating-transaction patterns that real irreversible payments require. Out of scope until Phase 2 is complete.

### 1.3 Architecture principle

The architecture must support Phase 2 without building Phase 2. Design clean extension seams (event producers can be added to the same bus; new worker handlers and read-model tables can be added) but do not implement unused functionality. **The default answer to any feature not in §3.1 is no. Execution details live in `docs/sprint-plan.md`; test requirements live in `docs/test-plan.md`; Claude Code enforcement lives in `CLAUDE.md`.**

---

## 2. Personas

Every authenticated user is **both a reader and a writer by default.** There is no "creator" role to be granted — authorship and subscribership are *derived* states:

- A user is an **author** when they own a publication.
- A user is a **subscriber** when they hold an active subscription to a publication.
- The same user routinely is both: they run a publication, and they subscribe to others.

The only assigned role is **admin** (a boolean `is_admin` flag), used for the operability surface.

| Persona | Does |
| --- | --- |
| **Reader / Subscriber** | Browses publications, subscribes (free or paid), sends gifts, reads posts (paid posts gated by subscription), sees a live feed of publications they follow. |
| **Writer / Author** | Creates a publication, configures subscription tiers, drafts and publishes posts, triggers newsletter sends, watches a real-time dashboard of subscribers/gifts/revenue with a transparent breakdown of platform fees and taxes. |
| **Admin / Operator** | Views failed events, retries/amends/discards them, inspects worker attempts and DLQ depths, resolves reconciliation reviews, monitors system health via CloudWatch. |

---

## 3. Scope

### 3.1 In scope (Phase 1)

**Product:** Cognito auth; publication creation and listing; author-configured multi-tier subscription plans; free and paid subscriptions with a transparent three-way bill (author / platform / tax); one-time gifts with the same split; idempotent commerce writes; post CRUD with draft/published/archived lifecycle; free vs paid post visibility; the publish action that triggers newsletter-send simulation; per-subscriber feed fanout; a real-time creator dashboard (SSE); an admin operability surface (failed-event runbook + reconciliation); S3 storage of receipt and newsletter artifacts.

**Engineering:** FastAPI API service; dedicated Python worker service; PostgreSQL with Alembic migrations (17 tables) in a shared schema package; Redis cache + pub/sub fanout; transactional outbox; SQS + DLQ; EventBridge bus; ledger transaction + multi-entry ledger; CloudWatch alarms + dashboard; OpenTelemetry tracing; Terraform IaC; GitHub Actions CI/CD; Dockerized local dev; k6 load testing; behavioral test suites in eight families (unit, integration, contract, regression, end-to-end smoke, infra, load, chaos).

### 3.2 Out of scope (Phase 1)

Real payments / Stripe / real payouts / refunds; multi-currency; per-jurisdiction or regional tax; subscription proration; auto-renewal / recurring billing; real email sending; discovery / recommendation / trending / tags / search; engagement (claps / comments / bookmarks); publication member roles; multi-region; Kubernetes; mobile app; chat; any saga / compensating-transaction machinery (deferred to Phase 3 with real money).

### 3.3 Anti-scope-creep rule

Any feature not listed in §3.1 is rejected unless it directly improves portfolio clarity or verifies system correctness. The default answer to new feature ideas is **no**.

---

## 4. Approved Stack

| Layer | Decision |
| --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind |
| Backend | FastAPI on ECS Fargate |
| Worker | Python worker on ECS Fargate |
| Database | PostgreSQL on Amazon RDS |
| Schema | `packages/pulsepress_schema` (SQLAlchemy 2.x models + Alembic), consumed by API and worker |
| Cache / fanout | Redis (local), ElastiCache Redis (AWS) |
| Queue | Amazon SQS (+ DLQ) |
| Events | Amazon EventBridge |
| Storage | Amazon S3 |
| Auth | Amazon Cognito (OAuth2/OIDC Authorization Code + PKCE) over HTTPS (ACM certificate on the ALB) |
| Infra | Terraform |
| Observability | OpenTelemetry, AWS Distro for OpenTelemetry, CloudWatch |
| CI/CD | GitHub Actions |
| Local dev | Docker Compose |
| Load tests | k6 |
| Python tooling | uv (workspace), Ruff, Pyright/mypy, pytest with family markers, Pydantic v2, SQLAlchemy 2.x, Alembic |
| Frontend tooling | pnpm, ESLint, Prettier, Vitest/Playwright |

---

## 5. System Architecture

See `docs/design-md/pulsepress-hld-architecture.md` / `docs/design/pulsepress-hld-architecture.html` (system context) and `docs/design-md/pulsepress-component-context.md` / `docs/design/pulsepress-component-context.html` (bounded contexts).

### 5.1 The central architectural principle: two write-shapes, one backbone

PulsePress separates writes by **shape**, and this distinction governs the entire design:

**Commerce writes are money-shaped.** Subscribe, change tier, cancel, gift. These get the full reliability treatment: an idempotency key, a transactional-outbox event written in the same DB transaction, an immutable multi-entry ledger, and asynchronous worker processing.

**Publishing writes are content-shaped.** Create/edit/draft/archive a publication or post. These are **plain authenticated CRUD** — no outbox, no idempotency key, no ledger. Forcing publishing through the commerce machinery would be over-engineering.

**The single seam between them is `publish()`.** Transitioning a post from draft to published is the *one* publishing action that emits a domain event (`post.published`), because publishing is what triggers newsletter distribution and subscriber fanout. Everything else in publishing is silent CRUD.

This split is the reason the event-driven backbone is justified rather than decorative: it has two real event producers (commerce and the publish seam), feeding one shared async pipeline.

### 5.2 Runtime services

**API service (FastAPI, ECS Fargate).** Validates Cognito JWTs; owns transactional writes; writes idempotency records and outbox events in the same transaction as commerce writes; serves the SSE stream; reads cached summaries from Redis. Business logic lives in `app/services/*` (commerce from Sprint 3, publishing from Sprint 6); routers stay thin.

**Worker service (Python, ECS Fargate).** Runs the outbox poller and the SQS consumer as separately runnable roles (`PULSEPRESS_WORKER_ROLE=poller|consumer|both`, Sprint 11); processes domain events under the worker contract of §11; writes the ledger transaction + multi-entry ledger; updates read models; renders and stores newsletter/receipt artifacts to S3; publishes real-time notifications to Redis after commit; handles retries and DLQ.

**Outbox poller.** Reads unpublished outbox events (`SELECT … FOR UPDATE SKIP LOCKED`), publishes to EventBridge, marks published. Publish-then-mark = at-least-once delivery, made safe by worker idempotency (ADR-0011). Failed publishes back off exponentially and become terminal after ten attempts.

### 5.3 The backbone flow

`commerce write or publish()` → `outbox_events row (same txn)` → `outbox poller` → `EventBridge` → `SQS` → `worker (idempotent)` → `ledger / read models / S3 / Redis` → `SSE → dashboard`. Two DLQs capture terminal failures (worker poison messages, EventBridge target delivery), surfaced to the operability layer.

---

## 6. Domain Model

See `pulsepress-er-model.html` and the Archify ERD. **17 tables**, clustered by context. All primary keys are UUID v4. All money is integer cents. All schema changes are Alembic migrations in `packages/pulsepress_schema/alembic`, committed with the change that needs them.

### 6.1 Identity (shared)

**`users`** — `id`, `cognito_sub` (UQ), `email`, `display_name`, `is_admin` (bool), `created_at`, `updated_at`. No role enum; author/subscriber are derived.

### 6.2 Publishing context (content-shaped)

**`publications`** — `id`, `owner_user_id` (FK users), `handle` (UQ), `name`, `description`, `avatar_url?`, `is_active`, audit. No `category` field (topics are Phase 2). The subscribable/giftable entity.

**`posts`** — `id`, `publication_id` (FK), `author_user_id` (FK, = owner in Phase 1), `title`, `slug`, `body`, `status {draft, published, archived}`, `visibility {free, paid}`, `published_at?`, `archived_at?`, audit.

**`post_versions`** — `id`, `post_id` (FK), `title`, `body`, `visibility`, `snapshotted_at`. Immutable snapshot written at publish time. The newsletter is rendered from the snapshot, not the live post, so a writer editing after publish does not change the already-sent newsletter. Also the foundation for Phase-2 edit history.

**`newsletter_sends`** — `id`, `post_id` (FK, **UNIQUE** in Phase 1 because there is no re-publish), `publication_id` (FK), `status {requested, sent, failed}`, `recipient_count_sim`, `artifact_s3_key?`, `recipients_snapshot_at?` (the handler's claim time, so a reclaimed attempt resolves the same recipient set), `sent_at?`, `created_at`. The record of a simulated newsletter distribution.

### 6.3 Commerce context (money-shaped)

**`subscription_plans`** — `id`, `publication_id` (FK), `name`, `monthly_price_cents` (author-set; 0 = free), `currency`, `allow_open_amount` (bool), `benefits` (jsonb; soft, displayed not enforced), `is_active`, audit.

**`subscriptions`** — `id`, `subscriber_user_id` (FK), `publication_id` (FK), `plan_id` (FK, mutable on tier change), `amount_cents` (current agreed tier amount), `charged_amount_cents` and `charged_currency` (immutable creation-time facts used to validate `subscription.created`), `status {active, canceled, expired}`, `period_start`, `period_end`, `canceled_at?`, `access_until?`. Constraints: partial unique index `UNIQUE(subscriber_user_id, publication_id) WHERE status='active'`; application guard `subscriber ≠ publication.owner`.

**`gift_transactions`** — `id`, `sender_user_id` (FK), `publication_id` (FK), `amount_cents`, `currency`, `message?`, `status {pending, processed, failed}`. Application guard: `sender ≠ owner`; minimum $0.50.

**`ledger_transactions`** — `id`, `publication_id` (FK), `source_type {subscription, gift}`, `source_id` (polymorphic logical link), `source_event_id`, `principal_amount_cents`, `author_net_cents`, `platform_fee_cents`, `tax_cents`, `total_charged_cents`, `currency`, `created_at`. **Immutable.** One row per paid subscription/gift. DB CHECK constraints enforce `author_net_cents + platform_fee_cents + tax_cents = total_charged_cents` and `principal_amount_cents + tax_cents = total_charged_cents`. `UNIQUE(source_type, source_id)` prevents duplicate ledger transactions.

**`ledger_entries`** — `id`, `ledger_transaction_id` (FK ledger_transactions), `publication_id` (FK), `account {author, platform, tax}`, `amount_cents`, `direction {credit}`, `created_at`. **Immutable.** Each ledger transaction writes exactly three rows. `UNIQUE(ledger_transaction_id, account)` prevents duplicate account rows. A deferred PostgreSQL constraint trigger rejects a transaction unless it has exactly three distinct accounts, matching publication IDs, and entries summing to `total_charged_cents`; this is required because a plain row-level CHECK cannot enforce a cross-row invariant.

### 6.4 Reliability kernel (shared)

**`outbox_events`** — `id`, `aggregate_type`, `aggregate_id`, `event_type`, `event_version`, `payload` (jsonb; the full envelope), `status {pending, published, failed, superseded, discarded}`, `publish_attempts`, `last_error?`, `next_attempt_at?`, `terminal_at?`, `created_at`, `published_at?`. Partial indexes back the poller predicates: `(created_at) WHERE status='pending'` and `(next_attempt_at) WHERE status='failed' AND terminal_at IS NULL`. Failed publishing retries with backoff; retry-exhausted rows stay `failed` with `terminal_at` for the audited operator workflow, never silently become `discarded`.

**`idempotency_keys`** — `id`, `user_id` (FK), `key`, `request_hash`, `response_status?`, `response_body?` (jsonb), `locked_until?`, audit. `UNIQUE(user_id, key)`. Used by all commerce mutations and admin verbs.

**`event_processing_attempts`** — `id`, `event_id` (UNIQUE; logical link to outbox, no hard FK across the async boundary), `event_type`, `status {started, succeeded, failed}`, `attempt_number`, `error_message?`, `locked_until?` (the claim lease), `terminal_at?`, `failure_event_emitted_at?`, `created_at`, `finished_at?`.

### 6.5 Read models (worker-populated)

**`publication_daily_stats`** — `id`, `publication_id` (FK), `stat_date`, `subscriber_count`, `gift_count`, `post_count`, `gross_revenue_cents`, `author_net_cents`, `platform_fees_cents`, `tax_collected_cents`. `UNIQUE(publication_id, stat_date)`. **Semantics: daily deltas.** `subscriber_count` is the net change that day (a cancel contributes `-1` on its date); totals are sums over days. `getPublicationSummary` does not read totals from this table; it counts non-expired subscriptions with the lazy-expiry predicate and reads revenue from `ledger_transactions`.

**`user_feed_events`** — `id`, `user_id` (FK), `publication_id` (FK), `source_event_id`, `event_type`, `payload` (jsonb), `created_at`, `read_at?`. `UNIQUE(user_id, source_event_id)` so a reclaimed fanout inserts nothing twice. Durable per-reader feed rows created by worker fanout. This is the Phase-1 subscriber notification feed, not Phase-2 discovery/recommendation.

**`notification_events`** — `id`, `publication_id` (FK), `source_event_id`, `event_type`, `payload` (jsonb), `created_at`. `UNIQUE(publication_id, source_event_id, event_type)`. Written by every commerce handler and the publish handler; backs the writer/admin publication dashboard and the public-safe activity stream.

### 6.6 Operability

**`reconciliation_log`** — `id`, `event_id`, `admin_user_id`, `action {retry, amend, discard, manual_fix}`, `reason` (required, ≥10 chars), `state_before` (jsonb), `state_after` (jsonb), `created_at`. Append-only, immutable. Every human override on permanent record; a `retry` records the state of both the outbox row and the attempt row.

---

## 7. Money Model

See `pulsepress-bill-breakdown.html` and `pulsepress-subscription-tiers.html`.

### 7.1 The split

The author sets a single number — the subscription price `P` (or the gift amount). Everything else is derived:

- **Buyer pays:** `P + tax`, where `tax = round(tax_pct × P)`. Tax is added on top (buyer-facing, like sales tax).
- **Platform keeps:** `platform_fee = round(platform_pct × P)`. Deducted from the author's share (author-facing, like Substack's cut). The platform does **not** take a cut of tax.
- **Author nets:** `author_net = P − platform_fee` (residual).
- **Invariant:** `author_net + platform_fee + tax == total_charged`, enforced as DB CHECK constraints on `ledger_transactions`; the deferred ledger-entry constraint trigger enforces the corresponding three-row materialization.

`platform_pct` and `tax_pct` are **flat global config values** in Phase 1. No jurisdictions, no per-author rates. Regional/jurisdictional tax is a future phase.

Integer-cent rounding rule: compute `tax` and `platform_fee` with round-half-up, then define `author_net` as the residual so the three entries always sum exactly to the total. The API computes the bill once; the worker validates the event's bill and writes it, never recomputing from current configuration.

### 7.2 Multi-tier subscriptions

A publication offers author-configured tiers (e.g. Free / $5 / $20). The discipline that keeps this from exploding: **tiers vary price and soft benefits, not content access.**

- **Content gating stays binary:** a post is `free` or `paid`; *any* active paid subscription unlocks *all* paid posts. There is no per-tier content gating.
- **Higher paid tiers are voluntary patronage**, labeled honestly (e.g. "Supporter"), not "more content." Identical access; the subscriber chooses to pay more to support the author and receive soft benefits (displayed, not enforced).
- This gives the multi-price-point ledger story (the three-way split runs across $5, $20, etc.) without per-tier entitlement logic.

### 7.3 Free vs paid = content-shaped vs money-shaped

A **free subscription** (price 0) involves no ledger entries, but it is still a commerce mutation: it requires an `Idempotency-Key`, writes the subscription row, and emits `subscription.created`. A **paid subscription** is money-shaped: full bill, three-way ledger transaction, three ledger entries, and idempotency key. Both rely on `UNIQUE(subscriber, publication) WHERE active` to prevent duplicate active subscriptions and both update counts/live feeds.

### 7.4 Subscription lifecycle money rules

- **Tier change** updates `plan_id` + `amount_cents` immediately, requires an `Idempotency-Key`, and emits `subscription.tier_changed`. Because Phase 1 has no recurring billing and no proration, tier change creates no new ledger transaction in the current period.
- **Cancel** transitions `active → canceled`; the subscriber retains access until `period_end`. No refund (Phase 1). Cancellation = no renewal, not immediate revocation.
- **Expiration** (`canceled → expired`) is derived lazily on read (no scheduler, no `subscription.expired` event). Every read that counts or entitles subscribers applies the predicate `status='active' AND (period_end IS NULL OR period_end >= now)` or `status='canceled' AND access_until >= now`.
- **Initial charge only** is simulated in Phase 1; recurring billing is deferred.

### 7.5 Newsletter recipient rules

Newsletter/fanout recipients are deterministic:

- Free posts fan out to all active subscribers.
- Paid posts fan out to active paid subscribers only.
- `canceled` subscriptions retain access and receive paid-post fanout until `access_until` / `period_end`.
- `expired` subscriptions are excluded.
- The worker snapshots recipient user IDs while handling `newsletter.send.requested`, at `recipients_snapshot_at`; later subscription changes do not mutate an already-started send, and a reclaimed attempt resolves the same set.
- The publication owner is excluded because self-subscribe is forbidden.
- Fanout inserts `user_feed_events` in chunks of 1,000 rows inside the one handler transaction; the Phase-1 ceiling is 10k recipients per publication. Splitting a send into per-chunk child events is a documented Phase-2 seam, not built now.

## 8. Event Model

See `docs/event-catalog.md`. **10 events.** All wrap a common envelope and use the shared outbox → EventBridge → SQS → worker architecture. Sprint 4 routed the six commerce/kernel types; **from Sprint 6 every catalog type is routed**, the allowlist is retired, and an unknown type is a worker failure, never a silently pending row.

### 8.1 Envelope (every event)

```
event_id, event_type, event_version, occurred_at, producer,
correlation_id, causation_id, aggregate_type, aggregate_id, payload
```

- `correlation_id` is generated by the API at request entry and copied to every downstream event and log line — one user action traces end-to-end.
- `causation_id` chains events causally (e.g. `ledger.transaction.recorded` carries the `gift.sent` event_id as its causation).
- Idempotency contract: every consumer dedupes by `event_id`; every handler is safe to invoke twice.
- Versioning: events start at v1; additive fields are non-breaking; removals/semantic changes bump the version; handlers dispatch on `(event_type, event_version)`.

### 8.2 The 10 events

**Publishing (4):** `post.published` (carries `version_id`, not body), `newsletter.send.requested`, `newsletter.sent`, `newsletter.send.failed`.

**Commerce (4):** `subscription.created` (carries the three-way split for the worker), `subscription.tier_changed` (no money impact this period), `subscription.canceled`, `gift.sent` (carries the split).

**Kernel (2):** `ledger.transaction.recorded` (one per balanced paid transaction, not per ledger row), `event.processing.failed` (DLQ signal feeding operability).

Deliberate omissions: `subscription.expired` (derived lazily), `post.archived` / `post.updated` / `post.draft_saved` (silent CRUD), `user.*` (Cognito's concern), all `engagement.*` (Phase 2), `payment.refunded` (Phase 3). See catalog for full justifications.

---

## 9. API Contract

Canonical: `docs/openapi.yaml` (OpenAPI 3.1.0, validated). Summary: `docs/design/pulsepress-api-contract.html`. **21 path entries, 29 operations, 32 schemas, 8 tags.** No endpoint is added by v1.4.

### 9.1 Cross-cutting rules

- **Auth:** `Authorization: Bearer <JWT>` on every endpoint. (No `/dev/session` route in the public contract; the local-dev auth shortcut lives in a separate router gated by `ENVIRONMENT=local`.)
- **Errors:** RFC 7807 Problem Details (`application/problem+json`) with `type, title, status, detail, instance, correlation_id`. Validation errors include `field_errors`.
- **Correlation:** every response carries `X-Correlation-Id`; every error body echoes it.
- **Idempotency:** `POST /subscriptions`, `PATCH /subscriptions/{id}`, `DELETE /subscriptions/{id}`, `POST /gifts`, and admin retry/amend/discard require `Idempotency-Key`. Replays carry `Idempotency-Replayed: true`; same key + different body → 422 `idempotency-conflict`. Same-key concurrent requests are serialized by the `idempotency_keys` unique claim and row lock so only one business write occurs; a stale committed in-flight claim returns 409 `idempotency-in-flight` until its `locked_until` expires.
- **State-level idempotence** (no commerce key needed): `publishPost`, `archivePost`. `cancelSubscription` is commerce-shaped and requires `Idempotency-Key`, while also returning a no-op 200 if already canceled under a later request.
- **Pagination:** opaque `cursor` + `limit` (max 100, default 25). SSE streams accept the same cursor to replay durable rows before attaching to Redis.

### 9.2 Endpoint groups

Auth (`/me`); Publications (list/create/detail/summary); Posts (CRUD + `/publish`); Plans (list/create); Subscriptions (create/get/tier-change/cancel); Gifts (send); Feed (recent events + SSE stream); Admin (outbox-events list/retry/amend/discard, reconciliation, worker-attempts). See the OpenAPI file for full request/response schemas, status codes, and examples.

---

## 10. State Machines

See `pulsepress-state-machines.html`.

**Post:** `draft → published → archived`. Self-loops on draft and published are CRUD edits (no events). `publish()` is the only event-emitting transition. `archived` is a soft delete; physical deletion is lazy after 30 days (ADR-0009). No re-publish.

**Subscription:** `active → canceled → expired`, with a self-loop on `active` for tier change. `subscribe()` branches free (idempotency + no ledger) vs paid (idempotency + ledger transaction + ledger entries). `cancel()` retains access until `period_end`. `expired` is derived lazily. `re-subscribe` creates a fresh row with a fresh amount snapshot.

**Gift:** `pending → processed | failed`. One-shot, no temporal state. `failed → pending` via admin replay.

**Outbox row:** `pending → published`; `pending → failed (retryable, next_attempt_at)` → `published` or `failed (terminal_at)`; terminal rows leave only through admin verbs: `retry → pending`, `amend → superseded` (new row created), `discard → discarded`.

**Processing attempt:** `started → succeeded`; `started → failed (retryable)` → `started` on reclaim after lease expiry or SQS redelivery; `failed` with `terminal_at` after the fifth attempt, emitting `event.processing.failed` once; admin `retry` clears `terminal_at` and resets `attempt_number`.

---

## 11. Reliability Design

**Idempotency** is layered: API-level (by `Idempotency-Key`) on all commerce mutations; worker-level (by `event_id` via `event_processing_attempts`) on all event handling. A duplicate user click is stopped at the API; an SQS redelivery is stopped at the worker. API claims are stored in `idempotency_keys` with `(user_id, key)` uniqueness, request hashes, response replay bodies, and `locked_until`; concurrent same-key writes serialize to one business effect and one cached replay.

**Commerce race handling:** application duplicate checks are backed by database constraints. If a duplicate active subscription races past the pre-check, the partial unique index remains authoritative and the API maps the database conflict to the same 409 duplicate-subscription response instead of surfacing a 500.

**Transactional outbox:** commerce writes and the `publish()` action write business data and the outbox event row in one PostgreSQL transaction, eliminating the dual-write inconsistency. The poller claims events with `FOR UPDATE SKIP LOCKED`, publishes then marks (at-least-once; ADR-0011), applies exponential retry backoff (5 s × 2^(n−1)), and marks a row terminal after ten attempts.

**Worker processing contract (ADR-0013).** Every handler, present and future, follows the same shape:

1. **Claim before side effects.** `INSERT … ON CONFLICT DO NOTHING` into `event_processing_attempts` with a 300 s lease (`locked_until`), committed in its own transaction. A concurrent delivery sees the live lease, raises in-progress, and leaves the SQS message for redelivery. A `succeeded` row means duplicate: the message is deleted with no effect.
2. **Validate the durable source** (subscription, gift, post version) before writing any artifact; a mismatch is a conflict, not a retry.
3. **Write artifacts write-once** before the handler transaction (`IfNoneMatch: *` on S3; `open("x")` locally). Identical bytes are accepted on retry; different bytes fail.
4. **One handler transaction** commits the business effect (ledger, feed rows, read models), any derived outbox events, and the attempt's `succeeded` status together.
5. **Delete the SQS message only after commit.**
6. **Terminal by attempt count.** The fifth failed attempt sets `terminal_at` and emits exactly one `event.processing.failed`; the SQS receive count is never used for this decision.
7. **Crash between artifact and commit self-heals:** the lease expires, a later delivery reclaims the row, the artifact PUT is idempotent, and uniqueness constraints (`UNIQUE(source_type, source_id)`, `UNIQUE(post_id)`, `UNIQUE(user_id, source_event_id)`) make the second durable write impossible. S3 and PostgreSQL are never made atomic; the lease is the recovery mechanism.

**Queue processing:** SQS for async work; `visibility_timeout_seconds` (360) is always greater than the lease plus the handler budget. Worker poison messages redrive to an SQS DLQ after five receives; EventBridge target-delivery failures use a separate DLQ after 24 retries within one hour. Both depths are metrics (§12).

**Documented failure modes:** duplicate purchase; worker crash after partial processing; EventBridge publish failure; SQS redelivery; Redis unavailable (SSE degrades, persistent log preserves data); S3 write failure; invalid/expired JWT; subscriber unsubscribes mid-newsletter-fanout (at-most-one stale notification, acceptable); writer edits post mid-fanout (snapshot protects the newsletter); poison event reaches DLQ and admin surface; worker outage drains without duplicates on restart.

---

## 12. Operability Layer

See `pulsepress-operability.html`. This layer turns the outbox+DLQ *pattern* into a runnable *system* — three sub-layers:

**Detection.** The worker and API emit **seven** CloudWatch metrics: `outbox_pending_count`, `outbox_oldest_pending_age_seconds`, `worker_handler_failures_total`, `worker_handler_duration_p95`, `sqs_age_of_oldest_message`, `dlq_depth{queue=worker}`, `dlq_depth{queue=eventbridge}`. Five named alarms (two critical, two warn, one info) fan out via SNS to email and a Slack webhook. The admin dashboard shows live counters regardless of alarm state. `outbox_pending_count` is a valid health signal only once all ten event types are routed (Sprint 6).

**Action — three runbook verbs, all audited, all requiring `Idempotency-Key` and a reason.**
1. **Retry** (safe / transient) resets whichever locus failed: a publish failure (`outbox_events.terminal_at`) goes back to `pending` with `next_attempt_at` and `terminal_at` cleared and `publish_attempts` preserved; a handler failure (`event_processing_attempts.terminal_at`) has `terminal_at` and `locked_until` cleared, `attempt_number` reset to 0, `failure_event_emitted_at` preserved so no second failure event is emitted, and the outbox row returned to `pending` so the poller re-publishes. Succeeded, discarded and superseded rows are not retryable.
2. **Amend & retry** (rare, dangerous, feature-flag-gated off by default): write a new event with corrected payload and `causation_id` = original; original marked `superseded`; requires reason + typed admin confirmation signature.
3. **Discard with reason** (terminal give-up): mark `discarded`; requires a reason of at least ten characters; opens a reconciliation review; emits a high-signal ops alert.

**Reconciliation.** When an event is discarded, the source business row (subscription/gift/newsletter send) may be stuck and disagree with reality. A structured runbook (`docs/runbooks/reconciliation.md`, Sprint 10) — inspect, decide (mark failed / manual ledger entry / re-emit), audit — resolves it. Every action writes an immutable `reconciliation_log` row with before/after state of every row it touched. No silent operator fixes.

**Admin confirmation signature.** For Phase 1, `admin_signature` is not cryptographic. It is a typed confirmation guard with the exact format `AMEND <event_id>`, combined with the authenticated admin identity from the JWT and the required reason. This avoids pretending Phase 1 has cryptographic operator signing while still preventing accidental destructive operator clicks.

## 13. Observability

**Logs** (structured JSON) include when available: `request_id`, `correlation_id`, `user_id`, `event_id`, `event_type`, `route`, `status_code`.

**Metrics:** API request count, p50/p95 latency, error rate; SQS queue depth; worker success/failure; worker latency; Redis cache hit/miss; plus the seven operability metrics (§12).

**Traces** (OpenTelemetry → ADOT → CloudWatch) span: gift/subscription creation request → outbox publication → worker event processing → ledger write → S3 artifact → SSE delivery. The envelope's `correlation_id` carries the trace context across the asynchronous boundary.

---

## 14. Security

**Authentication:** Cognito Authorization Code + PKCE for login; FastAPI validates JWT signature, issuer, audience/client, expiration, token use. No unsigned tokens in production. **No token traverses plain HTTP:** the ALB terminates TLS with an ACM certificate and redirects HTTP to HTTPS before the browser login flow ships (Sprint 8).

**Authorization:** derived author/subscriber checks + `is_admin` for the operability surface. No user can access another user's private transaction history or feed. Owners cannot self-subscribe or self-gift.

**Secrets:** none committed; `.env` files protected from AI reads/writes unless explicitly allowed; production secrets in AWS Secrets Manager / SSM; no raw secrets in Terraform.

**Cloud:** least-privilege IAM (the worker task role may publish to the project bus, consume the worker queue, and write under `receipts/*` and `newsletters/*` only); RDS and ElastiCache not publicly accessible; S3 private, versioned, encrypted, TLS-only; ECS tasks use task roles, not static credentials; every resource tagged with project and environment. Tasks run in public subnets with public IPs behind security groups that admit only the ALB; moving them to private subnets (NAT or VPC endpoints) is a Sprint-12 cost decision, not a Phase-1 blocker.

---

## 15. Repository Structure

```
pulsepress/
  apps/
    api/        app/{api,core,db,domain,integrations,schemas,services,auth}/ tests/ Dockerfile pyproject.toml
    worker/     pulsepress_worker/ tests/ Dockerfile pyproject.toml
    web/        app/ components/ lib/ tests/ package.json
  packages/
    pulsepress_schema/   models/ immutable.py alembic/ pyproject.toml     # one model set, one migration chain (ADR-0014)
  infra/terraform/
    environments/{dev,prod}/
    modules/{network,ecr,alb,ecs,rds,elasticache,cognito,messaging,observability}/
  docs/                  # tracked in git (ADR-0015)
    SPEC.md              # product scope + authoritative prose decisions
    architecture.md      # architecture, data model, event backbone, operability design
    architecture-revision.md
    sprint-plan.md       # one feature per sprint, traces, test families, gates
    test-plan.md         # test families, per-sprint matrix, concrete tests
    event-catalog.md     # 10 event contracts and envelope rules
    openapi.yaml         # canonical HTTP contract
    failure-modes.md     # failure injection and expected recovery behavior
    deployment.md        # cloud deploy/runbook notes
    local-dev.md         # docker compose + local shortcuts
    aws-production-setup-guide.md
    setup-test-guide.md
    runbooks/            # reconciliation.md (Sprint 10)
    phase2.md            # deferred Medium-style expansion plan
    portfolio-checklist.md
    design/              # portfolio-ready HTML diagram artifacts
    design-md/           # AI-readable Markdown companions for diagrams
    adr/                 # ADR-0001 … ADR-0015
  scripts/
    dev/          up.sh down.sh migrate.sh
    integration/  acceptance_local.sh
    chaos/        poison_event.sh break_worker.sh
    load/         phase1_acceptance.js
    ci/
  tasks/        todo.md  lessons.md  sprint-review.md
  .claude/      settings.json  commands/  agents/
  CLAUDE.md     # canonical Claude Code operating manual
  docker-compose.yml
  README.md
```

The uv workspace at the repository root declares `apps/api`, `apps/worker`, and `packages/pulsepress_schema` as members.

---

## 16. Sprint Plan

See `docs/sprint-plan.md` for canonical per-sprint task lists, traces, verification commands, non-goals, done-criteria, and portfolio artifacts. **Fourteen sprints (0–13).** Sprints 0–4 are complete. From Sprint 5 on, **each sprint delivers exactly one feature and ships it with every applicable test family** (unit, integration, contract, regression, end-to-end smoke, infra, load, chaos). Every task traces to an upstream artifact; anything that cannot be traced is scope creep.

| Sprint | Feature | Key principle |
| --- | --- | --- |
| **0 — Guardrails** | Design pack, CLAUDE.md, ADR stubs, task board. | No app code until done. |
| **1 — Foundation + walking skeleton** | Local stack + `/healthz` API on Fargate behind ALB. | De-risk cloud by deploying first. |
| **2 — Schema + auth** | 17-table schema, Cognito, JWT validation, `/me`, RDS + ElastiCache. | Earns the right to build APIs. |
| **3 — Commerce API + outbox** | Plans, subscribe/tier-change/cancel/gift, idempotency, outbox, bill. | Proves the atomic write boundary. |
| **4 — Worker + multi-entry ledger** | Poller, EventBridge→SQS→worker, idempotent handlers, three-row ledger, receipts, DLQ. | Activates the async backbone. |
| **5 — Shared schema package** | One model set, one migration chain, tracked docs, CI drift gates. | Fresh clone equals the author's machine. |
| **6 — Newsletter fanout** | All ten events routed; publish → artifact + feed rows via the two-hop contract. | Exactly-once effects on at-least-once delivery. |
| **7 — Live dashboard + feed** | Read models, Redis pub/sub, SSE with durable replay. | Redis is never truth. |
| **8 — Production auth** | ACM/HTTPS listener, Cognito PKCE in the browser. | No token over HTTP. |
| **9 — Admin: inspect + retry** | Admin lists, DLQ visibility, two-locus audited retry. | Safe verb first. |
| **10 — Admin: amend + discard** | Flag-gated amend, discard with reason, reconciliation runbook. | No silent operator fixes. |
| **11 — Observability + worker roles** | Structured logs, traces, seven metrics, five alarms, role split, chaos scripts. | Pattern becomes runnable system. |
| **12 — Hardening + load** | k6 thresholds, DB tuning, archival, failure evidence, scale-to-zero, cost. | Find failures before a reviewer does. |
| **13 — Portfolio polish** | README, diagram set, demo, resume bullets, fresh-clone test, ADRs. | Make the work findable and credible. |

**Enforcement surface:** canonical Claude Code rules live in `CLAUDE.md`. Pre-tool guard (block dangerous shell / `.env` reads / `terraform apply|destroy`), post-tool quality (targeted lint/format + behavioral-test static checks), stop verify (remind to update `tasks/todo.md`). Custom slash commands (`/plan-sprint`, `/implement-task`, `/verify-task`, `/review-diff`, `/write-adr`, `/prep-portfolio`) likewise authored as needed. Their requirements are recorded here; their implementation is not part of this spec.

---

## 17. Architecture Decision Records

ADRs live in `docs/adr/`, written as stubs in Sprint 0 and filled during implementation.

| ADR | Decision | Rationale (one line) |
| --- | --- | --- |
| 0001 | Terraform over CDK | Recruiter-recognizable IaC; clean plan/apply lifecycle. |
| 0002 | Cognito Auth Code + PKCE | Real OAuth2/OIDC; avoids custom auth. |
| 0003 | Transactional outbox | Eliminates DB/event dual-write inconsistency. |
| 0004 | SSE over WebSockets | One-way event streaming is sufficient; simpler infra. |
| 0005 | Redis = cache + fanout, not source of truth | Demonstrates Redis while preserving DB correctness. |
| 0006 | Walking-skeleton deploy at end of Sprint 1 | De-risks cloud deployment by doing it first, small. |
| 0007 | Scale-to-zero teardown + one-command rebuild | Cost-at-rest ≈ $0; itself a portfolio signal. |
| 0008 | Lazy time-based transitions (no schedulers in Phase 1) | Avoids scheduler infra; derive temporal state on read. |
| 0009 | Soft-delete then hard-delete after 30 days | Protects referenced rows; cleanup is lazy/manual. |
| 0010 | Behavioral testing only | Tests verify contract behavior, never implementation internals. |
| 0011 | Outbox publish-then-mark (at-least-once) | Free reliability given worker idempotency already required. |
| 0012 | Ledger transactions own the balance CHECKs; entries materialize three rows | Row-level CHECKs cannot sum sibling rows. |
| 0013 | Worker claim lease and write-once artifacts before commit | Exactly-once effects without S3/Postgres atomicity. |
| 0014 | Shared schema package consumed by API and worker | One model set, one migration chain, CI drift gate. |
| 0015 | Canonical docs and migrations are tracked in git | CI, fresh clones and cloud sessions equal the author's machine. |

A future Phase-3 ADR will cover Stripe integration and the saga/compensating-transaction pattern for real-money cancellation and refunds — deliberately not built in Phase 1, since PulsePress "payments" are reversible rows in our own database, not external irreversible transfers. A Sprint-12 ADR records the NAT-gateway versus VPC-endpoint decision for private task networking.

---

## 18. Acceptance & Phase Gates

### 18.1 Phase 1 acceptance test

The MVP is accepted when this flow works in the deployed cloud environment:

1. A user logs in through Cognito over HTTPS.
2. The user creates a publication and configures subscription tiers (free / paid).
3. The user drafts and publishes a post; `publish()` writes a snapshot and emits `post.published`.
4. The worker renders a newsletter from the snapshot, stores it in S3, fans out per-subscriber feed notifications, and emits `newsletter.sent`.
5. A second user opens the publication and subscribes to a paid tier with an idempotency key.
6. The API writes the subscription + outbox event in one PostgreSQL transaction and returns a transparent bill breakdown.
7. The worker processes the event through the SQS/EventBridge path, writes one balanced ledger transaction plus three ledger entries, updates read models, and stores a receipt in S3.
8. Redis invalidates the publication summary cache.
9. The writer dashboard shows the new subscriber and revenue, live via SSE, with the platform-fee/tax breakdown.
10. An operator can inspect and retry/discard a deliberately-failed event, with the action recorded in `reconciliation_log`.
11. CloudWatch traces show the full flow; an alarm fires for an injected poison event.
12. GitHub Actions shows a successful build/test pipeline with no skipped database suites; the k6 report meets its thresholds; the README documents architecture, failure handling, and deployment.

### 18.2 Phase 2 entry criteria

Medium-style features may begin only after Phase 1 is deployed to AWS; the core publish/subscribe/gift flow works end-to-end; observability screenshots and a load-test report exist; README and architecture docs are updated; and a sprint review documents Phase 1 limitations and Phase 2 candidates.

### 18.3 Phase 2 backlog (deferred)

Engagement (claps, bookmarks, comments, follow, read-time analytics); discovery (home feed, tag/topic pages — including the broad-vs-deep taxonomy decision, trending, recommendations, search); publication workflow (member roles, submission, editorial review, scheduled publishing); chunked fanout child events beyond 10k recipients. These attach to the existing backbone via new event producers, new worker handlers, and new denormalized read-model tables. **Do not implement during Phase 1; document extension seams only.**

---

## 19. Portfolio Targets

**Backend/SDE:** Built PulsePress, a cloud-deployed publishing & subscription platform (FastAPI, PostgreSQL, Redis, SQS, EventBridge, ECS Fargate) with publications, post publishing, idempotent subscription/gift APIs, a transactional outbox, async workers with a lease-based exactly-once contract, and a balanced ledger transaction plus multi-entry ledger with transparent fee/tax splitting.

**Cloud/SWE:** Deployed PulsePress on AWS with Terraform (ECS Fargate, RDS, ElastiCache, S3, Cognito, CloudWatch, EventBridge, SQS), GitHub Actions CI/CD with schema-drift gates, OpenTelemetry tracing, scale-to-zero teardown, and load-tested operational dashboards.

**System design:** Designed retry-safe event processing with SQS DLQs, layered idempotency, Redis cache invalidation, and a full operability layer (alerting, a three-verb admin runbook with two-locus retry, and audited state reconciliation) to surface and recover from failed event processing.

---

*End of specification. Markdown design companions are canonical for agent-readable design summaries; HTML diagrams are visual companions; this document is canonical for prose; `docs/openapi.yaml` is canonical for the HTTP contract; `docs/event-catalog.md` is canonical for event payloads.*
