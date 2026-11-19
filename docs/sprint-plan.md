# PulsePress Sprint Plan

**Version:** v1.2 (architecture revision v1.2; supersedes v1.1)
**Scope:** Phase 1
**Canonical for:** execution tasks, traces, verification commands, sprint gates.

## What changed in v1.2

- Sprints 0–4 are complete and kept here as history with their evidence.
- From Sprint 5 on, **every sprint delivers exactly one feature** and ships it with the
  **full test family set**: unit, integration, contract, regression, end-to-end smoke, and,
  where the feature touches them, infra, load, and chaos tests. A sprint is not done until
  every family in its matrix has evidence.
- The architecture revision (`docs/architecture-revision.md`) adds a prerequisite sprint
  (Sprint 5: shared schema package and migration integrity) and reorders the remaining work
  into single-feature sprints 6–13.
- Sprint-6 routes all ten catalog events; the Sprint-4 allowlist is retired.
- TLS is a prerequisite for the Cognito browser flow (Sprint 8), not an afterthought.
- Admin `retry` is specified as a two-locus reset (outbox publish failure and worker handler
  failure), split across Sprints 9 and 10 with amend/discard.

## Sprint execution rule

Every task must trace to at least one of:

- OpenAPI operationId.
- Event catalog event.
- ER table/model.
- State-machine transition.
- Sequence step.
- ADR.

No trace means no implementation. Yes, this is harsh. So are bugs.

## One feature per sprint

A sprint has one feature and one acceptance statement. The sprint's tasks are the
implementation slices of that feature plus the tests that prove it. Work that belongs to
another feature waits for its sprint, even when it is adjacent and tempting.

## Test families required every sprint (Sprint 5 onward)

| Family | Proves | Tooling | Marker / location |
|---|---|---|---|
| Unit | Pure logic without I/O: money math, envelope parsing, predicates, validators, parsers | pytest, Vitest | `@pytest.mark.unit`; `apps/web/**/*.test.ts` |
| Integration | Behaviour against real PostgreSQL (and Redis / S3 fakes) through public entry points | pytest with `TEST_DATABASE_URL`, worker handlers with catalog-valid events | `@pytest.mark.integration` |
| Contract | HTTP matches `docs/openapi.yaml`; events match `docs/event-catalog.md`; generated schemas do not drift | `scripts/ci/validate_openapi.py`, schema-generation drift check, payload validators in worker tests | `@pytest.mark.contract` |
| Regression | Previously fixed bugs stay fixed; earlier sprints' suites still pass | full `pytest` of api + worker, named `test_regression_*` tests | `@pytest.mark.regression` |
| End-to-end smoke | The feature works through the running stack | `scripts/integration/acceptance_local.sh` (extended each sprint), AWS smoke in the production guide | shell |
| Infra | Terraform is valid and policy-safe | `terraform fmt -check`, `validate`, `plan` when credentials exist, policy scripts | CI terraform job |
| Load | Latency and throughput targets hold | k6 | Sprint 12, then every sprint that changes a hot path |
| Chaos | Failure modes recover as documented | `scripts/chaos/*` | Sprint 11 onward |

Markers are declared in each app's `pyproject.toml`; CI runs the whole suite, and
`uv run pytest -m <family>` runs one family locally.

## Task template

```text
Task ID:
Trace:
Goal:
Scope:
Expected behavior:
Tests:
  Unit:
  Integration:
  Contract:
  Regression:
  E2E smoke:
  Infra / load / chaos (when applicable):
Verification:
Done criteria:
Non-goals:
```

---

# Sprint 0 — Guardrails (complete)

Goal: commit design pack, repo skeleton, AI-agent rules, task board, and verification scripts. No app feature code.

## S0-T01 — Normalize repository docs

Trace: SPEC §15, CLAUDE.md
Goal: establish architecture/execution/enforcement separation.

Scope:

- Add `docs/SPEC.md`, `docs/architecture.md`, `docs/openapi.yaml`, `docs/event-catalog.md`,
  `docs/sprint-plan.md`, `docs/test-plan.md`, canonical `CLAUDE.md`, and
  `tasks/todo.md`, `tasks/lessons.md`, `tasks/sprint-review.md`.

Tests: markdown links resolve for all local docs; OpenAPI parses.

Verification:

```bash
python scripts/ci/validate_openapi.py docs/openapi.yaml
python scripts/ci/check_docs_links.py docs CLAUDE.md
```

## S0-T02 — Add safety hooks and commands

Trace: CLAUDE.md, SPEC §16
Goal: prevent dangerous or scope-creep operations.

Scope: pre-tool guard blocks `.env` reads, secret printing, `terraform apply`, `terraform destroy`,
broad destructive shell commands; stop/verify reminder; slash commands `/plan-sprint`,
`/implement-task`, `/verify-task`, `/review-diff`, `/write-adr`, `/prep-portfolio`.

Verification: `python scripts/ci/test_agent_hooks.py`.

---

# Sprint 1 — Foundation + walking-skeleton deploy (complete)

Goal: local stack and `/healthz` API deployed to ECS Fargate behind ALB (build-only).

- S1-T01 Monorepo skeleton (`apps/api`, `apps/worker`, `apps/web`, `infra/terraform`, `scripts`, `docs`, `tasks`; uv; pnpm; Dockerfiles).
- S1-T02 FastAPI `GET /healthz` (internal, no auth, outside the product OpenAPI by design; ADR-0006).
- S1-T03 Terraform foundation: network, ECS cluster/service, ALB, ECR, CloudWatch log groups.

Verification: `terraform -chdir=infra/terraform/environments/dev fmt -check && validate`; api/worker/web lint, typecheck, test.

---

# Sprint 2 — Schema + auth (complete)

Goal: PostgreSQL schema, Cognito auth, JWT validation, `/me`, RDS + ElastiCache provisioned (build-only).

- S2-T01 Alembic base schema: 17 tables, UUID PKs, FK indexes, immutability triggers, partial-unique active subscription, ledger CHECKs.
- S2-T02 Cognito JWT validation (signature, issuer, audience, exp, token_use); local shortcut under `ENVIRONMENT=local`; `GET /v1/me`.
- S2-T03 RDS + ElastiCache + Cognito Terraform; secrets by reference.
- S2-T04 (user-directed) local stack + functional test; content-MVP acceleration (publication/post CRUD, publish event door, demo seed, API-backed web).
- S2-T05 (user-directed) README.

---

# Sprint 3 — Commerce API + outbox (complete)

Goal: publication/plan CRUD, subscription/gift commerce writes, idempotency, transactional outbox. Events accumulate unprocessed.

- S3-T01 Publication endpoints (`listPublications`, `createPublication`, `getPublication`, `updatePublication`, `getPublicationSummary`); detail embeds active plans.
- S3-T02 Plan endpoints (`listPlans`, `createPlan`); free or paid USD; `allow_open_amount`.
- S3-T03 Idempotency service: unique claim + row lock, `locked_until`, replay with `Idempotency-Replayed: true`, 422 on different body, 409 while a committed claim is in flight.
- S3-T04 Create subscription (`subscription.created`): self-subscribe 403, duplicate active 409 (DB race mapped to 409), bill computed once, atomic row + key + outbox.
- S3-T05 Change tier (`subscription.tier_changed`): no ledger in Phase 1.
- S3-T06 Cancel (`subscription.canceled`): access until `period_end`; later cancel is a 200 no-op without a second event.
- S3-T07 Send gift (`gift.sent`): self-gift 403, < 50 cents 422.
- S3-T08 Web integration: plans, subscribe, gift, paid-post entitlement, disabled destructive settings, no live font fetch.

Evidence: api `87 passed`; ruff/pyright clean; contract unchanged (21 paths).

---

# Sprint 4 — Worker + multi-entry ledger (complete; one known issue)

Goal: outbox poller, EventBridge→SQS→worker, idempotent handlers, ledger transactions, receipts, DLQ.

- S4-T01 Outbox poller: `FOR UPDATE SKIP LOCKED`, publish-then-mark, exponential backoff, terminal after 10 attempts, routes only the six commerce/kernel types.
- S4-T02 Worker idempotency: durable claim with lease (`locked_until`), attempt-count terminal accounting, SQS delete only after commit, source validation before the create-only receipt write.
- S4-T03 Subscription ledger handler: validates `charged_amount_cents`/`charged_currency`; one `ledger_transactions` + three `ledger_entries`; `ledger.transaction.recorded`; receipt in S3.
- S4-T04 Gift ledger handler: same, plus gift `processed`.
- S4-T05 DLQ and failure event: worker DLQ after five receives; distinct EventBridge target DLQ; one `event.processing.failed` per terminal failure.

Evidence (author machine): api `87 passed`; worker `24 passed`; Terraform fmt/validate clean.

**Known issue carried into Sprint 5.** The Sprint-4 Alembic migration (creation-charge columns,
outbox `next_attempt_at`/`terminal_at`, attempt lease columns, the deferred three-entry ledger
trigger) and the `docs/` spec pack are gitignored, so `main` fails CI and a fresh clone cannot
migrate to a schema the worker accepts. Sprint 5 closes this before any new feature.

---

# Sprint 5 — Feature: one schema, one migration chain (shared schema package)

Goal: the API and the worker consume one SQLAlchemy model set and one Alembic chain from
`packages/pulsepress_schema`; migrations and the spec pack are tracked; CI fails on drift.

Acceptance statement: a fresh clone runs `alembic upgrade head`, the worker suite passes on
that schema, and CI is green on `main`.

## S5-T01 — Track migrations and the spec pack

Trace: CLAUDE.md §8 (Alembic for every schema change), §2/§3 (read order, source of truth); ADR-0015
Expected behavior:

- `.gitignore` no longer excludes `apps/api/alembic/` or `docs/*`.
- The Sprint-4 migration(s) and `docs/` (SPEC, architecture, event catalog, test plan, ADRs, design-md) are committed.
- `scripts/ci/check_docs_links.py` covers the whole `docs/` tree again.

Tests:
- Contract: link check and OpenAPI validation pass over the full docs tree.
- Regression: `apps/api/tests/test_migrations.py` passes on a fresh clone (three-entry trigger, charge-snapshot backfill).

## S5-T02 — `packages/pulsepress_schema`

Trace: ADR-0014; SPEC §15; architecture revision §5.3
Expected behavior:

- Package contains `Base`, all 17 models, `IMMUTABLE_TABLES`, the immutability DDL, and the Alembic chain.
- `apps/api` and `apps/worker` depend on it through the uv workspace; `apps/worker/pulsepress_worker/models.py` is deleted.
- Each app keeps its own session factory and settings; the package imports neither FastAPI nor boto3.

Tests:
- Unit: package imports without FastAPI/boto3 on the path; `Base.metadata` lists exactly 17 tables.
- Integration: upgrade head → downgrade base → upgrade head on a disposable database; worker suite runs against the migrated schema.
- Contract: `alembic check` (autogenerate against head) reports no changes.
- Regression: full api and worker suites unchanged in count and green.

## S5-T03 — CI drift gates

Trace: CLAUDE.md §11 (verification families); test-plan §1.3
Expected behavior:

- `api` job runs `alembic check` and `alembic heads` (exactly one head).
- `worker` job gains a Postgres service so its database tests run instead of skipping.
- Guardrails job runs the docs link check over `docs/`.

Tests:
- Infra/CI: a deliberately drifted model in a throwaway branch fails `alembic check`.
- E2E smoke: `scripts/integration/acceptance_local.sh` runs the Sprint 2–4 walkthrough end to end on a fresh clone.

Verification:

```bash
cd packages/pulsepress_schema && uv run alembic check && uv run alembic heads
cd apps/api && uv run ruff check && uv run pyright && uv run pytest
cd apps/worker && uv run ruff check && uv run pyright && uv run pytest
python scripts/ci/check_docs_links.py docs CLAUDE.md README.md
scripts/integration/acceptance_local.sh
```

Done criteria: CI green on `main`; fresh-clone worker suite `24 passed`; no duplicate model definitions remain.
Non-goals: no new endpoints, events, or handlers.
Portfolio artifact: the green CI run and a one-paragraph "why we track migrations" note in the README.

---

# Sprint 6 — Feature: newsletter fanout

Goal: `publishPost` leads to a rendered newsletter artifact in S3 and durable per-reader feed rows,
through the two-hop catalog contract, with exactly-once effects on at-least-once delivery.

Acceptance statement: publishing a post to a publication with free and paid subscribers writes one
`newsletter_sends` row, one S3 artifact, one `user_feed_events` row per entitled recipient, and
emits `newsletter.sent`; replaying any event adds nothing.

## S6-T01 — Route all ten catalog events

Trace: event catalog §2; ADR-0011; architecture revision F8
Expected behavior:

- Poller routes every catalog `event_type`; the Sprint-4 allowlist constant is removed.
- EventBridge rule lists all ten detail-types.
- The worker raises `UnsupportedEventError` for unknown types; routing and handlers land in the same change so no catalog type becomes a poison message.

Tests:
- Unit: envelope dispatch table covers `(event_type, event_version)` for all ten.
- Regression: the Sprint-4 "unimplemented types stay pending" test is replaced by "all catalog types publish"; unknown type still terminal after five attempts.
- Infra: `terraform validate`; rule pattern contains ten entries.

## S6-T02 — Publishing service extraction

Trace: CLAUDE.md §9 (business logic in services); OpenAPI `publishPost`, `getPost`, `createPost`
Expected behavior:

- `app/services/publishing.py` owns publish transition, snapshot, outbox write, slug generation, entitlement, summary aggregation; routers become thin.
- No behaviour change; responses byte-identical.

Tests:
- Regression: existing publishing API tests pass unchanged; a contract test diffs responses before/after for the walkthrough payloads.

## S6-T03 — `post.published` handler

Trace: event `post.published` → `newsletter.send.requested`; ER `newsletter_sends`
Expected behavior:

- Creates `newsletter_sends` in `requested` with `UNIQUE(post_id)`; emits `newsletter.send.requested` with `causation_id`.
- Replay finds the existing row and emits nothing new.

Tests:
- Integration: catalog-valid `post.published` twice → one `newsletter_sends` row, one derived outbox row.
- Contract: emitted payload validates against the catalog.

## S6-T04 — `newsletter.send.requested` handler

Trace: events `newsletter.send.requested`, `newsletter.sent`, `newsletter.send.failed`; ER `post_versions`, `user_feed_events`; SPEC §7.5
Expected behavior:

- Reads `post_versions` by `version_id`, never `posts.body`.
- Snapshots recipients at `recipients_snapshot_at` with the deterministic predicate (free: all active; paid: paid active + canceled with access; expired and owner excluded).
- Writes `newsletters/{publication_id}/{post_id}/{version_id}.html` write-once.
- Inserts `user_feed_events` in chunks of 1,000 with `ON CONFLICT DO NOTHING` on `(user_id, source_event_id)`.
- Marks `newsletter_sends` sent with `recipient_count_sim` and `artifact_s3_key`; emits `newsletter.sent`.
- Retryable S3 failure leaves the row `requested`; terminal failure marks `failed` and emits `newsletter.send.failed`.

Tests:
- Unit: recipient predicate with fixture rows (active, canceled before/after `access_until`, expired, owner, free vs paid).
- Integration: free post → all active; paid post → paid active + canceled-with-access only; owner excluded; post edited after publish → artifact unchanged; duplicate delivery → no new feed rows; crash after artifact PUT → reclaim completes without duplicates; S3 failure → retryable then terminal path.
- Contract: `newsletter.sent` / `newsletter.send.failed` payloads validate; `listUserFeedEvents` returns the rows.
- Regression: Sprint-4 ledger tests still pass with the extended dispatch table.
- E2E smoke: local worker cycle after a publish produces the artifact file and feed rows.

## S6-T05 — Additive migration for fanout idempotency

Trace: ER `newsletter_sends`, `user_feed_events`, `outbox_events`; architecture revision §5.4.2
Expected behavior:

- `newsletter_sends`: `UNIQUE(post_id)`, `recipients_snapshot_at timestamptz`.
- `user_feed_events`: `UNIQUE(user_id, source_event_id)`.
- `outbox_events`: partial indexes for the poller predicates.

Tests:
- Integration: migration roundtrip; constraint rejections.
- Contract: `alembic check` clean.

## S6-T06 — Worker IAM for newsletters

Trace: SPEC §14; architecture revision §8
Expected behavior: worker task role gains `s3:PutObject`/`GetObject` under `newsletters/*`; nothing else widens.

Tests: Infra: `terraform validate`; policy document contains the two prefixes only.

Verification:

```bash
cd apps/worker && uv run pytest -m "unit or integration or contract or regression"
cd apps/api && uv run pytest
terraform -chdir=infra/terraform/environments/dev validate
scripts/integration/acceptance_local.sh --through sprint-6
```

Done criteria: acceptance statement verified locally; all families have evidence; no event or endpoint added beyond the catalog and OpenAPI.
Non-goals: Redis, SSE, dashboard rows (Sprint 7).
Portfolio artifact: rendered newsletter artifact screenshot + feed rows query output.

---

# Sprint 7 — Feature: live dashboard and reader feed (Redis pub/sub + SSE)

Goal: writers see subscribers, gifts, revenue and publishes update live; readers see their feed
live; reloads and reconnects replay from durable rows; Redis loss degrades, never corrupts.

Acceptance statement: with the stack running, a paid subscribe appears on the owner's dashboard
over SSE within two seconds, the publication summary reflects it, and the same events are
returned by the list endpoints after a reconnect.

## S7-T01 — Commerce and publishing read models

Trace: events `subscription.*`, `gift.sent`, `post.published`; ER `notification_events`, `publication_daily_stats`; architecture revision §5.5
Expected behavior:

- Every commerce handler and the publish handler write one `notification_events` row (public-safe payload; owner-only fields flagged).
- Migration adds `notification_events.source_event_id` and `UNIQUE(publication_id, source_event_id, event_type)`.
- `publication_daily_stats` are daily deltas: cancel writes `-1` on the cancel date; totals are sums.
- `getPublicationSummary` applies the lazy-expiry predicate and reads revenue from `ledger_transactions`.

Tests:
- Unit: stats delta computation; expiry predicate.
- Integration: each handler writes exactly one notification row; redelivery adds none; summary excludes expired subscriptions and matches ledger revenue.
- Regression: Sprint-4 handlers' ledger behaviour unchanged.

## S7-T02 — Redis adapter

Trace: ADR-0005; SPEC §5.2
Expected behavior:

- Worker publishes `pub:{publication_id}` and `user:{user_id}` after commit (best effort, logged on failure).
- API caches `summary:{publication_id}` for 60 s; worker invalidates after each commerce commit.
- Redis unavailable: cache miss path and no exception on publish.

Tests:
- Integration (Redis container): publish → subscriber receives; invalidation after a handler commit; Redis stopped → handlers still commit and API still answers.

## S7-T03 — SSE and list endpoints

Trace: OpenAPI `listNotificationEvents`, `streamNotificationEvents`, `listUserFeedEvents`, `streamUserFeedEvents`; ADR-0004
Expected behavior:

- Stream replays durable rows after the client cursor, then attaches to Redis; `: keepalive` every 15 s.
- Redis down: polls the durable table every 5 s and emits a `degraded` comment line.
- Owner sees the full publication stream; subscribers see the public-safe subset; users see only their own feed.

Tests:
- Unit: cursor encode/decode; `data:` JSON serializer.
- Integration: SSE client receives an event; reconnect with cursor returns no duplicates; authorization matrix.
- Contract: response schemas and SSE event shape match OpenAPI.
- Regression: list endpoints paginate with `cursor` + `limit` (max 100).
- Load smoke: 100 concurrent SSE connections hold for five minutes without error.

## S7-T04 — Writer dashboard and feed UI

Trace: SPEC §3.1 (real-time creator dashboard); test-plan §5
Expected behavior: dashboard shows subscriber/gift/revenue with fee and tax breakdown and a live activity list; loading/empty/success/error states; reconnect preserves the durable list.

Tests: Vitest unit for the SSE hook and cursor persistence; Playwright E2E: subscribe in one context, dashboard updates in another.

Verification:

```bash
cd apps/api && uv run pytest -m "integration and redis"
cd apps/worker && uv run pytest
pnpm --dir apps/web test && pnpm --dir apps/web exec playwright test
scripts/integration/acceptance_local.sh --through sprint-7
```

Done criteria: acceptance statement verified; Redis-down test green; dashboard screenshot captured.
Non-goals: metrics, alarms, admin surface.
Portfolio artifact: SSE dashboard screenshot and the Redis-outage degradation log excerpt.

---

# Sprint 8 — Feature: production authentication (TLS + Cognito PKCE in the browser)

Goal: a user signs in through the Cognito hosted UI over HTTPS and uses the deployed web app.

Acceptance statement: in the deployed environment, `https://<web-host>` redirects to Cognito,
returns to `/auth/callback`, exchanges the code with PKCE, calls `/v1/me`, and signs out.

## S8-T01 — HTTPS listener

Trace: SPEC §14; ADR-0006 consequence; architecture revision F10
Expected behavior: ACM certificate for a configured domain; ALB listener 443; HTTP 80 → 301 to HTTPS; domain and certificate ARN are variables.

Tests: Infra: `terraform validate`; `plan` shows the listener and redirect; policy script asserts no HTTP-only product listener remains.

## S8-T02 — Cognito callback and logout URLs

Trace: ADR-0002; AWS guide §19
Expected behavior: environment layer exposes `callback_urls` / `logout_urls`; defaults are HTTPS web origins.

Tests: Infra: variables are required in `prod`; `validate` clean.

## S8-T03 — Web production auth adapter

Trace: ADR-0002; SPEC §14
Expected behavior: builds the authorization URL with S256 PKCE and `state`; handles `/auth/callback`; exchanges the code at `/oauth2/token`; stores the ID token in session storage; calls `/v1/me`; clears tokens and redirects to the Cognito logout endpoint; the local shortcut remains available only when `NEXT_PUBLIC_AUTH_MODE=local`.

Tests:
- Unit (Vitest): verifier/challenge generation, `state` verification, token storage, mode switch.
- Integration: API JWT verifier fixtures (happy, expired, bad issuer, bad audience, wrong token_use) remain green.
- Contract: local auth router absent when `ENVIRONMENT != local`.
- Regression: Sprint-2 auth suite.
- E2E: Playwright against a mocked hosted UI locally; manual acceptance in AWS per the production guide §16/§19.

Verification:

```bash
pnpm --dir apps/web test && pnpm --dir apps/web build
cd apps/api && uv run pytest tests/test_auth.py
terraform -chdir=infra/terraform/environments/dev validate
```

Done criteria: acceptance statement verified in AWS once; no token ever traverses HTTP.
Non-goals: admin surface, metrics.
Portfolio artifact: hosted-UI login screenshot and the HTTPS listener in `terraform plan` output.

---

# Sprint 9 — Feature: admin runbook, inspection and retry

Goal: an admin can see failed outbox rows, worker attempts, DLQ depths and reconciliation entries,
and can safely retry a failed event with an audit trail.

Acceptance statement: a deliberately poisoned event reaches terminal failure, is listed in the
admin surface, is retried with an `Idempotency-Key` and reason, re-publishes, succeeds, and the
`reconciliation_log` row shows before/after state.

## S9-T01 — Admin list endpoints and DLQ visibility

Trace: OpenAPI `listOutboxEvents`, `listWorkerAttempts`, `listReconciliations`; SPEC §12
Expected behavior: `is_admin` guard (403 otherwise); status filters and cursor pagination; both DLQ depths exposed as CloudWatch metrics and, if the contract permits, as response metadata.

Tests:
- Integration: non-admin 403; admin 200 with filters; pagination boundaries.
- Contract: schemas validate; no new endpoint outside OpenAPI.

## S9-T02 — `retryOutboxEvent` (two loci)

Trace: OpenAPI `retryOutboxEvent`; ER `outbox_events`, `event_processing_attempts`, `reconciliation_log`; architecture revision §5.2
Expected behavior:

- Requires `Idempotency-Key` and reason.
- Publish-failed locus: `status=pending`, `next_attempt_at=NULL`, `terminal_at=NULL`, `publish_attempts` preserved.
- Handler-failed locus: attempt `terminal_at=NULL`, `attempt_number=0`, `locked_until=NULL`, `failure_event_emitted_at` preserved; outbox row set to `pending` so the poller re-publishes.
- Writes one `reconciliation_log` row with both rows' before/after state.
- Retry of a succeeded or discarded event is rejected.

Tests:
- Unit: eligibility matrix (pending, published+succeeded, failed-terminal, attempt-terminal, discarded, superseded).
- Integration: both loci reset and reprocess; audit row content; same-key replay returns the stored response; no second `event.processing.failed`.
- Contract: 422 on missing key or short reason.
- Regression: worker idempotency suite.
- Chaos/E2E: `scripts/chaos/poison_event.sh` → terminal → retry → success.

## S9-T03 — Admin web page (list + retry)

Trace: test-plan §5
Expected behavior: list with filters; retry form requires reason; disabled for ineligible rows.
Tests: Vitest for form validation; Playwright for the retry flow.

Verification:

```bash
cd apps/api && uv run pytest tests/test_admin*.py
cd apps/worker && uv run pytest
scripts/chaos/poison_event.sh && scripts/integration/acceptance_local.sh --through sprint-9
```

Done criteria: acceptance statement verified locally; retry is the only mutating verb shipped.
Non-goals: amend, discard, alarms.
Portfolio artifact: admin list screenshot with a retried event and its audit row.

---

# Sprint 10 — Feature: admin runbook, amend and discard with reconciliation

Goal: the two dangerous verbs exist behind their guards, and every give-up opens a reconciliation review.

Acceptance statement: with the amend flag off, amend returns 403; with it on and a typed
`AMEND <event_id>`, a corrected event is created and the original is `superseded`; discard with a
ten-character reason marks the row `discarded` and a reconciliation review is listed.

## S10-T01 — `amendOutboxEvent`

Trace: OpenAPI `amendOutboxEvent`; SPEC §12
Expected behavior: feature flag off by default; requires reason and exact `AMEND <event_id>`; new outbox row with `causation_id` = original; original `superseded`; audit row.
Tests: Unit: signature parser. Integration: flag off 403; bad signature 422; happy path creates one new row and supersedes one. Contract: payload of the amended event validates against the catalog.

## S10-T02 — `discardOutboxEvent` and reconciliation review

Trace: OpenAPI `discardOutboxEvent`, `listReconciliations`; ER `reconciliation_log`
Expected behavior: reason ≥ 10 chars; row `discarded`; reconciliation review opened against the source business row; ops alert signal emitted; retry of a discarded row rejected.
Tests: Integration: short reason 422; discard creates the review; immutability of the log. Regression: Sprint-9 retry eligibility. E2E: admin UI forms require reason and confirmation.

## S10-T03 — Reconciliation runbook

Trace: SPEC §12 (inspect, decide, audit)
Expected behavior: `docs/runbooks/reconciliation.md` with the decision table (mark failed, manual ledger entry, re-emit) and the audit requirement; `manual_fix` action recorded through the same log.

Verification: as Sprint 9 plus `scripts/integration/acceptance_local.sh --through sprint-10`.
Done criteria: all three verbs audited; flag default verified off in every environment file.
Portfolio artifact: reconciliation review screenshot and the runbook.

---

# Sprint 11 — Feature: observability and worker runtime hardening

Goal: the system reports its own health, alarms on the named signals, traces one request
end-to-end, and the worker loop no longer serializes polling behind the SQS long-poll.

Acceptance statement: an injected poison event raises a CloudWatch alarm within five minutes;
a trace shows subscribe → outbox → worker → ledger → S3; the poller role and consumer role run as
separate loops.

## S11-T01 — Structured logging

Trace: CLAUDE.md §13
Expected behavior: JSON logs with `request_id`, `correlation_id`, `user_id`, `event_id`, `event_type`, `route`, `status_code` where available.
Tests: Unit: formatter; Integration: a request's correlation id appears in the API log, the envelope, and the worker log.

## S11-T02 — OpenTelemetry traces

Trace: SPEC §13
Expected behavior: API and worker instrumented; ADOT sidecar in both task definitions; trace context carried in the envelope's `correlation_id`.
Tests: Integration: in-memory exporter captures the expected span names. Infra: task definitions include the collector.

## S11-T03 — Metrics and alarms

Trace: SPEC §12; architecture revision F11
Expected behavior: seven metrics (`outbox_pending_count`, `outbox_oldest_pending_age_seconds`, `worker_handler_failures_total`, `worker_handler_duration_p95`, `sqs_age_of_oldest_message`, `dlq_depth{queue=worker}`, `dlq_depth{queue=eventbridge}`); five named alarms; SNS to email and webhook.
Tests: Unit: metric emitter batching. Integration: fake CloudWatch client receives the seven names. Infra: `validate`; alarm count equals five; `scripts/ci/check_cost_tags.py` passes.

## S11-T04 — Worker role split

Trace: architecture revision F13/§7
Expected behavior: `PULSEPRESS_WORKER_ROLE=poller|consumer|both`; two ECS services or two threads; `visibility_timeout > event_lock_seconds + handler budget` documented in Terraform variables.
Tests: Integration: each role runs alone; outbox age under idle consumer stays under two seconds. Regression: Sprint-4 worker suite.

## S11-T05 — Chaos scripts and failure-mode evidence

Trace: `docs/failure-modes.md`
Expected behavior: `scripts/chaos/poison_event.sh`, `scripts/chaos/break_worker.sh`; the eleven failure modes documented with injection, expected, observed, evidence, recovery.
Tests: Chaos: each script's expected signal appears (DLQ message, alarm, retry success).

Verification:

```bash
cd apps/api && uv run pytest && cd ../worker && uv run pytest
terraform -chdir=infra/terraform/environments/dev validate && python scripts/ci/check_cost_tags.py infra/terraform
scripts/chaos/poison_event.sh && scripts/chaos/break_worker.sh
```

Done criteria: acceptance statement evidenced with screenshots; alarm names match the spec.
Portfolio artifact: CloudWatch dashboard and alarm screenshots; one end-to-end trace.

---

# Sprint 12 — Feature: hardening and load

Goal: the Phase-1 targets are measured, the database is tuned for them, and cost is known.

Acceptance statement: k6 runs subscribe, gift, publish and SSE scenarios at the Phase-1 load
with p95 inside targets and zero data-integrity violations; scale-to-zero and rebuild succeed.

- S12-T01 k6 scripts with thresholds (API p95 < 300 ms reads, < 500 ms commerce writes; outbox→handler p95 < 5 s; fanout 10k < 30 s).
- S12-T02 DB review: `EXPLAIN` for hot paths; outbox partial indexes confirmed; archival script for `published` rows older than 30 days that never touches `pending`/`failed`.
- S12-T03 Failure-mode evidence pack (screenshots, logs) for all eleven cases.
- S12-T04 Scale-to-zero teardown and one-command rebuild verified; cost report; NAT vs VPC-endpoint decision recorded as an ADR.

Tests: Load: k6 thresholds are pass/fail. Integration: archival script invariants. Regression: full suites. Infra: `plan` diff after rebuild is empty.

Verification:

```bash
k6 run scripts/load/phase1_acceptance.js
python scripts/ci/check_cost_tags.py infra/terraform
```

Portfolio artifact: load-test report and cost table.

---

# Sprint 13 — Feature: portfolio polish

Goal: make the project legible to reviewers.

- S13-T01 README architecture and local/cloud runbooks.
- S13-T02 Architecture diagram set (Archify requirements tree, ERD, LLD, sequence, HLD, distributed view) moved under `docs/design/`.
- S13-T03 Demo recording checklist and recording.
- S13-T04 Resume bullets from verified outcomes only.
- S13-T05 Phase-2 entry criteria review.
- S13-T06 Fresh-clone test on a clean machine.
- S13-T07 ADRs 0001–0015 filled.

Tests: E2E: fresh-clone script reaches the Sprint-7 acceptance statement. Regression: full suites. Contract: docs link check.

Done criteria: cloud acceptance flow works; README explains design and failure handling; load-test report, observability screenshots, demo recording exist; fresh clone starts local dev.
