# PulsePress — Project Specification

**Spec version:** v1.2 (diagram-sync version; supersedes v1.1)
**Product:** Event-driven creator publishing & subscription platform (Substack-model)
**Purpose:** SWE/SDE portfolio project
**Development model:** Spec-driven, Claude Code–assisted, deployed on AWS
**Primary goal:** Build a concise, cloud-deployed, production-shaped publishing-and-subscription platform where writers publish posts and earn through paid subscriptions and gifts, processed through an event-driven backend with full operability — then extend with Medium-style engagement and discovery features in Phase 2.

---

## 0. How to read this spec

This document is the authoritative text specification. It is accompanied by paired AI-readable Markdown companions and portfolio-ready HTML diagrams under `docs/design-md/` and `docs/design/`. Markdown companions are the canonical design summaries for coding agents; HTML diagrams are visual companions for humans, screenshots, and the README. The OpenAPI file (`docs/openapi.yaml`) is canonical for the HTTP contract.

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
| **Admin / Operator** | Views failed events, retries/amends/discards them, inspects worker attempts, resolves reconciliation reviews, monitors system health via CloudWatch. |

---

## 3. Scope

### 3.1 In scope (Phase 1)

**Product:** Cognito auth; publication creation and listing; author-configured multi-tier subscription plans; free and paid subscriptions with a transparent three-way bill (author / platform / tax); one-time gifts with the same split; idempotent commerce writes; post CRUD with draft/published/archived lifecycle; free vs paid post visibility; the publish action that triggers newsletter-send simulation; per-subscriber feed fanout; a real-time creator dashboard (SSE); an admin operability surface (failed-event runbook + reconciliation); S3 storage of receipt and newsletter artifacts.

**Engineering:** FastAPI API service; dedicated Python worker service; PostgreSQL with Alembic migrations (17 tables); Redis cache + pub/sub fanout; transactional outbox; SQS + DLQ; EventBridge bus; ledger transaction + multi-entry ledger; CloudWatch alarms + dashboard; OpenTelemetry tracing; Terraform IaC; GitHub Actions CI/CD; Dockerized local dev; k6 load testing; behavioral test suites.

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
| Cache / fanout | Redis (local), ElastiCache Redis (AWS) |
| Queue | Amazon SQS (+ DLQ) |
| Events | Amazon EventBridge |
| Storage | Amazon S3 |
| Auth | Amazon Cognito (OAuth2/OIDC Authorization Code + PKCE) |
| Infra | Terraform |
| Observability | OpenTelemetry, AWS Distro for OpenTelemetry, CloudWatch |
| CI/CD | GitHub Actions |
| Local dev | Docker Compose |
| Load tests | k6 |
| Python tooling | uv, Ruff, Pyright/mypy, pytest, Pydantic v2, SQLAlchemy 2.x, Alembic |
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

**API service (FastAPI, ECS Fargate).** Validates Cognito JWTs; owns transactional writes; writes idempotency records and outbox events in the same transaction as commerce writes; serves the SSE stream; reads cached summaries from Redis.

**Worker service (Python, ECS Fargate).** Runs the outbox poller; consumes SQS; processes domain events idempotently; writes the ledger transaction + multi-entry ledger; updates read models; renders and stores newsletter/receipt artifacts to S3; publishes real-time notifications to Redis; handles retries and DLQ.

**Outbox poller (worker mode in MVP).** Reads unpublished outbox events (`SELECT … FOR UPDATE SKIP LOCKED`), publishes to EventBridge, marks published. Publish-then-mark = at-least-once delivery, made safe by worker idempotency (ADR-0011).

### 5.3 The backbone flow

`commerce write or publish()` → `outbox_events row (same txn)` → `outbox poller` → `EventBridge` → `SQS` → `worker (idempotent)` → `ledger / read models / S3 / Redis` → `SSE → dashboard`. DLQ captures terminal failures, surfaced to the operability layer.

---

## 6. Domain Model

See `pulsepress-er-model.html`. **17 tables**, clustered by context. All primary keys are UUID v4. All money is integer cents. All schema changes are Alembic migrations.

### 6.1 Identity (shared)

**`users`** — `id`, `cognito_sub` (UQ), `email`, `display_name`, `is_admin` (bool), `created_at`, `updated_at`. No role enum; author/subscriber are derived.

### 6.2 Publishing context (content-shaped)

**`publications`** — `id`, `owner_user_id` (FK users), `handle` (UQ), `name`, `description`, `avatar_url?`, `is_active`, audit. No `category` field (topics are Phase 2). The subscribable/giftable entity.

**`posts`** — `id`, `publication_id` (FK), `author_user_id` (FK, = owner in Phase 1), `title`, `slug`, `body`, `status {draft, published, archived}`, `visibility {free, paid}`, `published_at?`, `archived_at?`, audit.

**`post_versions`** — `id`, `post_id` (FK), `title`, `body`, `visibility`, `snapshotted_at`. Immutable snapshot written at publish time. The newsletter is rendered from the snapshot, not the live post, so a writer editing after publish does not change the already-sent newsletter. Also the foundation for Phase-2 edit history.

**`newsletter_sends`** — `id`, `post_id` (FK), `publication_id` (FK), `status {requested, sent, failed}`, `recipient_count_sim`, `artifact_s3_key?`, `sent_at?`. The record of a simulated newsletter distribution.

### 6.3 Commerce context (money-shaped)

**`subscription_plans`** — `id`, `publication_id` (FK), `name`, `monthly_price_cents` (author-set; 0 = free), `currency`, `allow_open_amount` (bool), `benefits` (jsonb; soft, displayed not enforced), `is_active`, audit.

**`subscriptions`** — `id`, `subscriber_user_id` (FK), `publication_id` (FK), `plan_id` (FK, mutable on tier change), `amount_cents` (**snapshot** of agreed amount at subscribe time), `status {active, canceled, expired}`, `period_start`, `period_end`, `canceled_at?`, `access_until?`. Constraints: partial unique index `UNIQUE(subscriber_user_id, publication_id) WHERE status='active'`; application guard `subscriber ≠ publication.owner`.

**`gift_transactions`** — `id`, `sender_user_id` (FK), `publication_id` (FK), `amount_cents`, `currency`, `message?`, `status {pending, processed, failed}`. Application guard: `sender ≠ owner`; minimum $0.50.

**`ledger_transactions`** — `id`, `publication_id` (FK), `source_type {subscription, gift}`, `source_id` (polymorphic logical link), `source_event_id`, `principal_amount_cents`, `author_net_cents`, `platform_fee_cents`, `tax_cents`, `total_charged_cents`, `currency`, `created_at`. **Immutable.** One row per paid subscription/gift. DB CHECK constraints enforce `author_net_cents + platform_fee_cents + tax_cents = total_charged_cents` and `principal_amount_cents + tax_cents = total_charged_cents`. `UNIQUE(source_type, source_id)` prevents duplicate ledger transactions.

**`ledger_entries`** — `id`, `ledger_transaction_id` (FK ledger_transactions), `publication_id` (FK), `account {author, platform, tax}`, `amount_cents`, `direction {credit}`, `created_at`. **Immutable.** Each ledger transaction writes exactly three rows. `UNIQUE(ledger_transaction_id, account)` prevents duplicate account rows. Do not attempt to enforce cross-row balance with a plain PostgreSQL CHECK on this table; balance lives on `ledger_transactions`, and worker/invariant tests verify the three-entry materialization.

### 6.4 Reliability kernel (shared)

**`outbox_events`** — `id`, `aggregate_type`, `aggregate_id`, `event_type`, `event_version`, `payload` (jsonb), `status {pending, published, failed, superseded, discarded}`, `publish_attempts`, `last_error?`, `created_at`, `published_at?`.

**`idempotency_keys`** — `id`, `user_id` (FK), `key`, `request_hash`, `response_status?`, `response_body?` (jsonb), `locked_until?`, audit. `UNIQUE(user_id, key)`. Used by all commerce mutations.

**`event_processing_attempts`** — `id`, `event_id` (logical link to outbox, no hard FK across the async boundary), `event_type`, `status {started, succeeded, failed}`, `attempt_number`, `error_message?`, `created_at`, `finished_at?`.

### 6.5 Read models (worker-populated)

**`publication_daily_stats`** — `id`, `publication_id` (FK), `stat_date`, `subscriber_count`, `gift_count`, `post_count`, `gross_revenue_cents`, `author_net_cents`, `platform_fees_cents`, `tax_collected_cents`. `UNIQUE(publication_id, stat_date)`.

**`user_feed_events`** — `id`, `user_id` (FK), `publication_id` (FK), `source_event_id`, `event_type`, `payload` (jsonb), `created_at`, `read_at?`. Durable per-reader feed rows created by worker fanout. This is the Phase-1 subscriber notification feed, not Phase-2 discovery/recommendation.

**`notification_events`** — `id`, `publication_id` (FK), `event_type`, `payload` (jsonb), `created_at`. Backs the writer/admin publication dashboard and public-safe publication activity stream.

### 6.6 Operability

**`reconciliation_log`** — `id`, `event_id`, `admin_user_id`, `action {retry, amend, discard, manual_fix}`, `reason` (required, ≥10 chars), `state_before` (jsonb), `state_after` (jsonb), `created_at`. Append-only, immutable. Every human override on permanent record.

---

## 7. Money Model

See `pulsepress-bill-breakdown.html` and `pulsepress-subscription-tiers.html`.

### 7.1 The split

The author sets a single number — the subscription price `P` (or the gift amount). Everything else is derived:

- **Buyer pays:** `P + tax`, where `tax = round(tax_pct × P)`. Tax is added on top (buyer-facing, like sales tax).
- **Platform keeps:** `platform_fee = round(platform_pct × P)`. Deducted from the author's share (author-facing, like Substack's cut). The platform does **not** take a cut of tax.
- **Author nets:** `author_net = P − platform_fee` (residual).
- **Invariant:** `author_net + platform_fee + tax == total_charged`, enforced as DB CHECK constraints on `ledger_transactions`, not as an impossible cross-row CHECK on `ledger_entries`.

`platform_pct` and `tax_pct` are **flat global config values** in Phase 1. No jurisdictions, no per-author rates. Regional/jurisdictional tax is a future phase.

Integer-cent rounding rule: compute `tax` and `platform_fee` with round-half-up, then define `author_net` as the residual so the three entries always sum exactly to the total.

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
- **Expiration** (`canceled → expired`) is derived lazily on read (no scheduler, no `subscription.expired` event).
- **Initial charge only** is simulated in Phase 1; recurring billing is deferred.

---


### 7.5 Newsletter recipient rules

Newsletter/fanout recipients are deterministic:

- Free posts fan out to all active subscribers.
- Paid posts fan out to active paid subscribers only.
- `canceled` subscriptions retain access and receive paid-post fanout until `access_until` / `period_end`.
- `expired` subscriptions are excluded.
- The worker snapshots recipient user IDs while handling `post.published`; later subscription changes do not mutate an already-started send.
- The publication owner is excluded because self-subscribe is forbidden.

## 8. Event Model

See `docs/event-catalog.md`. **10 events.** All wrap a common envelope and flow through the shared outbox → EventBridge → SQS → worker pipeline.

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

Canonical: `docs/openapi.yaml` (OpenAPI 3.1.0, validated). Summary: `docs/design/pulsepress-api-contract.html`. **21 path entries, 29 operations, 32 schemas, 8 tags.**

### 9.1 Cross-cutting rules

- **Auth:** `Authorization: Bearer <JWT>` on every endpoint. (No `/dev/session` route in the public contract; the local-dev auth shortcut lives in a separate router gated by `ENVIRONMENT=local`.)
- **Errors:** RFC 7807 Problem Details (`application/problem+json`) with `type, title, status, detail, instance, correlation_id`. Validation errors include `field_errors`.
- **Correlation:** every response carries `X-Correlation-Id`; every error body echoes it.
- **Idempotency:** `POST /subscriptions`, `PATCH /subscriptions/{id}`, `DELETE /subscriptions/{id}`, `POST /gifts`, and admin retry/amend/discard require `Idempotency-Key`. Replays carry `Idempotency-Replayed: true`; same key + different body → 422 `idempotency-conflict`.
- **State-level idempotence** (no commerce key needed): `publishPost`, `archivePost`. `cancelSubscription` is commerce-shaped and requires `Idempotency-Key`, while also returning a no-op 200 if already canceled under a later request.
- **Pagination:** opaque `cursor` + `limit` (max 100, default 25).

### 9.2 Endpoint groups

Auth (`/me`); Publications (list/create/detail/summary); Posts (CRUD + `/publish`); Plans (list/create); Subscriptions (create/get/tier-change/cancel); Gifts (send); Feed (recent events + SSE stream); Admin (outbox-events list/retry/amend/discard, reconciliation, worker-attempts). See the OpenAPI file for full request/response schemas, status codes, and examples.

---

## 10. State Machines

See `pulsepress-state-machines.html`.

**Post:** `draft → published → archived`. Self-loops on draft and published are CRUD edits (no events). `publish()` is the only event-emitting transition. `archived` is a soft delete; physical deletion is lazy after 30 days (ADR-0009). No re-publish.

**Subscription:** `active → canceled → expired`, with a self-loop on `active` for tier change. `subscribe()` branches free (idempotency + no ledger) vs paid (idempotency + ledger transaction + ledger entries). `cancel()` retains access until `period_end`. `expired` is derived lazily. `re-subscribe` creates a fresh row with a fresh amount snapshot.

**Gift:** `pending → processed | failed`. One-shot, no temporal state. `failed → pending` via admin replay.

---

## 11. Reliability Design

**Idempotency** is layered: API-level (by `Idempotency-Key`) on all commerce mutations; worker-level (by `event_id` via `event_processing_attempts`) on all event handling. A duplicate user click is stopped at the API; an SQS redelivery is stopped at the worker.

**Transactional outbox:** commerce writes and the `publish()` action write business data and the outbox event row in one PostgreSQL transaction, eliminating the dual-write inconsistency. The poller publishes then marks (at-least-once; ADR-0011).

**Queue processing:** SQS for async work; DLQ after retry exhaustion; worker deletes the SQS message only after successful processing; poison messages surface in the operability layer.

**Documented failure modes:** duplicate purchase; worker crash after partial processing; EventBridge publish failure; SQS redelivery; Redis unavailable (SSE degrades, persistent log preserves data); S3 write failure; invalid/expired JWT; subscriber unsubscribes mid-newsletter-fanout (at-most-one stale notification, acceptable); writer edits post mid-fanout (snapshot protects the newsletter).

---

## 12. Operability Layer

See `pulsepress-operability.html`. This layer turns the outbox+DLQ *pattern* into a runnable *system* — three sub-layers:

**Detection.** The worker and API emit six CloudWatch metrics: `dlq_depth`, `outbox_pending_count`, `outbox_oldest_pending_age_seconds`, `worker_handler_failures_total`, `worker_handler_duration_p95`, `sqs_age_of_oldest_message`. Five named alarms (two critical, two warn, one info) fan out via SNS to email and a Slack webhook. The admin dashboard shows live counters regardless of alarm state.

**Action — three runbook verbs, all audited.**
1. **Retry** (safe / transient): reset to pending; poller re-publishes; worker dedupe protects.
2. **Amend & retry** (rare, dangerous, feature-flag-gated off by default): write a new event with corrected payload; original marked `superseded`; requires reason + typed admin confirmation signature.
3. **Discard with reason** (terminal give-up): mark `discarded`; requires a reason; opens a reconciliation review; emits a high-signal ops alert.

**Reconciliation.** When an event is discarded, the source business row (subscription/gift) may be stuck and disagree with reality. A structured runbook — inspect, decide (mark failed / manual ledger entry / re-emit), audit — resolves it. Every action writes an immutable `reconciliation_log` row with before/after state. No silent operator fixes.

---


**Admin confirmation signature.** For Phase 1, `admin_signature` is not cryptographic. It is a typed confirmation guard with the exact format `AMEND <event_id>`, combined with the authenticated admin identity from the JWT and the required reason. This avoids pretending Phase 1 has cryptographic operator signing while still preventing accidental destructive operator clicks.

## 13. Observability

**Logs** (structured JSON) include when available: `request_id`, `correlation_id`, `user_id`, `event_id`, `event_type`, `route`, `status_code`.

**Metrics:** API request count, p50/p95 latency, error rate; SQS queue depth; DLQ count; worker success/failure; worker latency; outbox pending count; Redis cache hit/miss; plus the six operability metrics (§12).

**Traces** (OpenTelemetry → ADOT → CloudWatch) span: gift/subscription creation request → outbox publication → worker event processing → ledger write → S3 artifact → SSE delivery.

---

## 14. Security

**Authentication:** Cognito Authorization Code + PKCE for login; FastAPI validates JWT signature, issuer, audience/client, expiration, token use. No unsigned tokens in production.

**Authorization:** derived author/subscriber checks + `is_admin` for the operability surface. No user can access another user's private transaction history. Owners cannot self-subscribe or self-gift.

**Secrets:** none committed; `.env` files protected from AI reads/writes unless explicitly allowed; production secrets in AWS Secrets Manager / SSM; no raw secrets in Terraform.

**Cloud:** least-privilege IAM; RDS and ElastiCache not publicly accessible; S3 private by default; ALB exposes only required HTTP routes; ECS tasks use task roles, not static credentials; every resource tagged with project and environment.

---

## 15. Repository Structure

```
pulsepress/
  apps/
    api/        app/{api,core,db,domain,integrations,models,schemas,services,auth}/ tests/ alembic/ Dockerfile pyproject.toml
    worker/     app/ tests/ Dockerfile pyproject.toml
    web/        app/ components/ lib/ tests/ package.json
  infra/terraform/
    environments/{dev,prod}/
    modules/{network,ecs,rds,elasticache,sqs,eventbridge,s3,cognito,observability}/
  docs/
    SPEC.md              # product scope + authoritative prose decisions
    architecture.md      # architecture, data model, event backbone, operability design
    sprint-plan.md       # execution tasks, traces, success criteria, verification commands
    test-plan.md         # concrete API/worker/invariant/frontend/infra tests
    event-catalog.md     # 10 event contracts and envelope rules
    openapi.yaml         # canonical HTTP contract
    failure-modes.md     # failure injection and expected recovery behavior
    deployment.md        # cloud deploy/runbook notes
    local-dev.md         # docker compose + local shortcuts
    phase2.md            # deferred Medium-style expansion plan
    portfolio-checklist.md
    design/              # portfolio-ready HTML diagram artifacts
    design-md/           # AI-readable Markdown companions for diagrams
    adr/                 # ADR-0001 … ADR-0012
  scripts/
    dev/        up.sh down.sh
    chaos/      poison_event.sh break_worker.sh
    integration/  ci/
  tasks/        todo.md  lessons.md  sprint-review.md
  .claude/      settings.json  commands/  agents/
  CLAUDE.md     # Claude Code rules
  CLAUDE.md     # canonical Claude Code operating manual
  docker-compose.yml
  README.md
```

---

## 16. Sprint Plan

See `docs/sprint-plan.md` for canonical per-sprint task lists, traces, verification commands, non-goals, done-criteria, and portfolio artifacts. The old HTML sprint-plan visualization is optional and non-canonical. **8 sprints, ~6 weeks for a solo developer with AI assistance.** Every task traces to an upstream artifact (an OpenAPI endpoint, a catalog event, an ER table, a state, a sequence step); anything that cannot be traced is scope creep.

| Sprint | Goal | Key principle |
| --- | --- | --- |
| **0 — Guardrails** | Commit the design pack, CLAUDE.md, ADR stubs, task board. | No app code until done. |
| **1 — Foundation + walking-skeleton deploy** | Local stack + deploy `/healthz`-only API to AWS Fargate behind ALB. | **De-risk cloud by deploying first.** |
| **2 — Schema + auth** | 17-table schema (Alembic), Cognito, JWT validation, `/me`, RDS + ElastiCache. | Earns the right to build APIs. |
| **3 — Commerce API + outbox** | Publication/plan CRUD, subscribe/tier-change/cancel/gift, idempotency, transactional outbox, bill breakdown. Events accumulate unprocessed. | Proves the atomic write boundary. |
| **4 — Worker + multi-entry ledger** | Outbox poller, EventBridge→SQS→worker, idempotent handlers, three-row ledger, S3 receipts, DLQ. | Activates the async backbone. |
| **5 — Publishing + newsletter + SSE** | Post CRUD, `publish()` event-door, newsletter render+fanout, Redis pub/sub, SSE dashboard, post gating, soft-delete. | The content side + real-time. |
| **6 — Operability** | CloudWatch alarms, admin runbook (retry/amend/discard), reconciliation, chaos scripts. | Turns pattern into runnable system. |
| **7 — Hardening + load** | k6 load tests, p95 capture, DB tuning, failure-mode evidence, cost analysis, scale-to-zero verification. | Find failures before a reviewer does. |
| **8 — Polish + portfolio** | README, architecture diagram, demo recording, resume bullets, Phase-2 entry criteria, fresh-clone test, fill all ADRs. | Make the work findable and credible. |

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

A future Phase-3 ADR will cover Stripe integration and the saga/compensating-transaction pattern for real-money cancellation and refunds — deliberately not built in Phase 1, since PulsePress "payments" are reversible rows in our own database, not external irreversible transfers.

---

## 18. Acceptance & Phase Gates

### 18.1 Phase 1 acceptance test

The MVP is accepted when this flow works in the deployed cloud environment:

1. A user logs in through Cognito.
2. The user creates a publication and configures subscription tiers (free / paid).
3. The user drafts and publishes a post; `publish()` writes a snapshot and emits `post.published`.
4. The worker renders a newsletter, stores it in S3, fans out per-subscriber feed notifications, and emits `newsletter.sent`.
5. A second user opens the publication and subscribes to a paid tier with an idempotency key.
6. The API writes the subscription + outbox event in one PostgreSQL transaction and returns a transparent bill breakdown.
7. The worker processes the event through the SQS/EventBridge path, writes one balanced ledger transaction plus three ledger entries, updates analytics, and stores a receipt in S3.
8. Redis invalidates the publication summary cache.
9. The writer dashboard shows the new subscriber and revenue, live via SSE, with the platform-fee/tax breakdown.
10. An operator can inspect and retry/discard a deliberately-failed event, with the action recorded in `reconciliation_log`.
11. CloudWatch traces show the full flow; an alarm fires for an injected poison event.
12. GitHub Actions shows a successful build/test/deploy; the README documents architecture, failure handling, and deployment.

### 18.2 Phase 2 entry criteria

Medium-style features may begin only after Phase 1 is deployed to AWS; the core publish/subscribe/gift flow works end-to-end; observability screenshots and a load-test report exist; README and architecture docs are updated; and a sprint review documents Phase 1 limitations and Phase 2 candidates.

### 18.3 Phase 2 backlog (deferred)

Engagement (claps, bookmarks, comments, follow, read-time analytics); discovery (home feed, tag/topic pages — including the broad-vs-deep taxonomy decision, trending, recommendations, search); publication workflow (member roles, submission, editorial review, scheduled publishing). These attach to the existing backbone via new event producers, new worker handlers, and new denormalized read-model tables. **Do not implement during Phase 1; document extension seams only.**

---

## 19. Portfolio Targets

**Backend/SDE:** Built PulsePress, a cloud-deployed publishing & subscription platform (FastAPI, PostgreSQL, Redis, SQS, EventBridge, ECS Fargate) with publications, post publishing, idempotent subscription/gift APIs, a transactional outbox, async workers, and a balanced ledger transaction plus multi-entry ledger with transparent fee/tax splitting.

**Cloud/SWE:** Deployed PulsePress on AWS with Terraform (ECS Fargate, RDS, ElastiCache, S3, Cognito, CloudWatch, EventBridge, SQS), GitHub Actions CI/CD, OpenTelemetry tracing, scale-to-zero teardown, and load-tested operational dashboards.

**System design:** Designed retry-safe event processing with SQS DLQs, layered idempotency, Redis cache invalidation, and a full operability layer (alerting, a three-verb admin runbook, and audited state reconciliation) to surface and recover from failed event processing.

---

*End of specification. Markdown design companions are canonical for agent-readable design summaries; HTML diagrams are visual companions; this document is canonical for prose; `docs/openapi.yaml` is canonical for the HTTP contract; `docs/event-catalog.md` is canonical for event payloads.*
