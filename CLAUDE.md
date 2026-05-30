# CLAUDE.md — PulsePress Claude Code Operating Manual

You are working on **PulsePress**, a cloud-deployed, event-driven publishing and subscription platform modeled after Substack. This is a **spec-driven Claude Code project**. This file is the canonical AI-agent operating manual for Claude Code. A future `AGENTS.md` may mirror these rules for Codex usage, but it is not part of the Claude Code control plane and Claude Code must not rely on it.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

The authoritative project artifacts are:

1. `docs/openapi.yaml` — HTTP contract and API schemas.
2. `docs/event-catalog.md` — event envelope, event names, payloads, and handler contracts.
3. `docs/architecture.md` — architecture, data model, write-shape rules, ledger design, and operability design.
4. `docs/SPEC.md` — product scope, phase boundaries, acceptance gates, portfolio goals.
5. `docs/sprint-plan.md` — execution plan, task traces, sprint done criteria.
6. `docs/test-plan.md` — required behavioral tests and verification matrix.
7. `docs/design-md/*.md` — AI-readable design companion summaries.
8. `docs/design/*.html` — portfolio visuals only, not implementation truth.
9. `tasks/todo.md` — active sprint/task board.
10. `tasks/lessons.md` — corrections and prevention rules.
11. `tasks/sprint-review.md` — end-of-sprint evidence.

If a task cannot be traced to one of these artifacts, stop and ask. Do not improvise. Do not vibe-code. Do not expand scope because something seems useful. The default answer to "should I also add..." is **no**.

---

## 1. Project goal

Build a concise, cloud-deployed Substack-style platform demonstrating:

- FastAPI API service on ECS Fargate.
- Python worker service on ECS Fargate.
- PostgreSQL on RDS.
- Redis / ElastiCache for cache and fanout only.
- SQS + DLQ.
- EventBridge.
- S3 artifacts.
- Cognito OAuth2/OIDC Authorization Code + PKCE.
- Terraform infrastructure.
- GitHub Actions CI/CD.
- CloudWatch + OpenTelemetry.
- A transparent three-way money split.
- A balanced multi-entry ledger.
- A real operability layer: detection, retry, amend, discard, reconciliation.

Phase 1 is the only implementation target. Medium-style engagement/discovery features are Phase 2 only. Real payments are Phase 3 and entirely out of scope.

---

## 2. Read order before non-trivial work

For every non-trivial task, read in this order:

1. `CLAUDE.md`.
2. `tasks/todo.md`.
3. The relevant section of `docs/sprint-plan.md`.
4. The relevant section of `docs/SPEC.md`.
5. The relevant section of `docs/architecture.md`.
6. `docs/openapi.yaml` if the task touches API behavior, schemas, auth, headers, or errors.
7. `docs/event-catalog.md` if the task touches outbox, worker behavior, event payloads, or async processing.
8. `docs/test-plan.md` for required tests.
9. Relevant `docs/design-md/*.md` companion if the task references a diagram.
10. Relevant ADR under `docs/adr/` if the task touches an architectural decision.

Do not treat HTML/SVG diagram layout text as implementation truth. HTML diagrams exist for screenshots and human review. Use `docs/design-md/*.md` as the AI-readable companion. If Markdown and HTML disagree, trust Markdown and update the HTML later.

---

## 3. Source-of-truth hierarchy

When artifacts disagree, use this hierarchy:

1. `docs/openapi.yaml` for HTTP endpoints, request/response schemas, headers, auth, status codes, and errors.
2. `docs/event-catalog.md` for event names, envelope, payload fields, and handler invariants.
3. `docs/architecture.md` for data model, ledger design, outbox, worker, cache, observability, and operability rules.
4. `docs/SPEC.md` for product scope, phase gates, and portfolio acceptance.
5. `docs/sprint-plan.md` for execution sequencing.
6. `docs/test-plan.md` for verification requirements.
7. `docs/design-md/*.md` for diagram-readable summaries.
8. `docs/design/*.html` for visual portfolio companions only.

If there is a conflict that cannot be resolved by this hierarchy, stop and surface it to the user. Never silently choose the convenient interpretation.

---

## 4. Scope rules

### Phase 1 allowed scope

Only the following are in scope:

- Cognito auth.
- Publication create/list/detail/update summary.
- Author-configured multi-tier subscription plans.
- Free and paid subscriptions.
- One-time gifts.
- Transparent three-way bill: author, platform, tax.
- Idempotent commerce writes.
- Transactional outbox.
- EventBridge + SQS + DLQ async path.
- Worker idempotency.
- `ledger_transactions` + three `ledger_entries` rows per paid transaction.
- Post CRUD with draft/published/archived lifecycle.
- Free vs paid post visibility.
- `publishPost` as the single publishing event-door.
- Newsletter-send simulation: feed fanout + S3 artifact, no real email.
- `user_feed_events` durable reader feed.
- Redis cache + pub/sub fanout.
- SSE dashboard.
- Admin operability surface: retry, amend, discard, reconciliation.
- CloudWatch metrics/alarms and OpenTelemetry traces.
- Terraform deployment.
- GitHub Actions CI/CD.
- k6 load testing.
- README, diagrams, demo evidence, portfolio artifacts.

### Explicitly out of scope before Phase 1 acceptance

Do not implement:

- Stripe or real payments.
- Real payouts.
- Refunds.
- Auto-renewal.
- Subscription proration.
- Multi-currency.
- Jurisdictional/regional tax.
- Real email sending.
- Claps, comments, bookmarks, follows.
- Search, tags, topics, trending, recommendations, discovery/home feed.
- Publication member roles, editorial workflow, submissions, scheduled publishing.
- Read-time analytics.
- Mobile app.
- Chat.
- Kubernetes.
- Multi-region.
- Saga/compensating-transaction machinery.

If asked to add out-of-scope work, decline and point to `docs/SPEC.md` and `docs/phase2.md`. If the user explicitly overrides scope, record the override in `tasks/lessons.md` and update the relevant spec file before coding.

---

## 5. The central architecture rule: two write-shapes

This project exists to demonstrate disciplined system boundaries. Internalize this before writing code.

### 5.1 Commerce writes are money-shaped

Commerce writes include:

- create free subscription,
- create paid subscription,
- change tier,
- cancel subscription,
- send gift,
- admin retry/amend/discard recovery verbs.

Commerce writes must:

- Require `Idempotency-Key`.
- Validate request and response schemas from `docs/openapi.yaml`.
- Use integer cents only. Never floats.
- Compute bill breakdown in the API once and carry it in event payloads.
- Write business row + idempotency record + outbox event atomically when an event is emitted.
- Never write ledger rows in API routes.
- Emit only event types defined in `docs/event-catalog.md`.
- Be safe under duplicate client submission.

Free subscriptions still require `Idempotency-Key`. They emit `subscription.created`, update counts/feed, but do not create ledger transactions.

### 5.2 Publishing writes are content-shaped

Publishing writes include:

- create publication,
- update publication metadata,
- create draft post,
- edit draft post,
- edit published post,
- archive post.

Publishing writes must:

- Use normal authenticated CRUD.
- Not require `Idempotency-Key`.
- Not write ledger rows.
- Not emit events.
- Not write outbox rows.

### 5.3 The one publishing exception: `publishPost`

`publishPost` is the only publishing action that emits an event.

It must atomically:

- transition post from `draft` to `published`,
- write immutable `post_versions` snapshot,
- write `post.published` outbox event with `version_id`, not full post body.

Newsletter rendering must read from `post_versions`, never the mutable `posts` row.

---

## 6. Ledger and money rules

### 6.1 Money representation

- All money is integer cents.
- Currency is `USD` only in Phase 1.
- Do not use floats in money code, tests, schemas, DB models, or UI calculations.
- Use round-half-up for `tax_cents` and `platform_fee_cents`.
- Define `author_net_cents` as residual: `principal_amount_cents - platform_fee_cents`.

### 6.2 Bill split

For principal price `P`:

- `tax_cents = round_half_up(tax_pct * P)`.
- `platform_fee_cents = round_half_up(platform_pct * P)`.
- `author_net_cents = P - platform_fee_cents`.
- `total_charged_cents = P + tax_cents`.

The invariant is:

```text
principal_amount_cents + tax_cents = total_charged_cents
author_net_cents + platform_fee_cents + tax_cents = total_charged_cents
```

### 6.3 Correct ledger model

Do not enforce cross-row balance with a plain PostgreSQL `CHECK` on `ledger_entries`. PostgreSQL row-level checks cannot sum sibling rows. That design is forbidden.

Correct model:

- `ledger_transactions` stores one balanced transaction and owns the CHECK constraints.
- `ledger_entries` materializes exactly three rows per transaction: `author`, `platform`, `tax`.
- Worker writes `ledger_transactions` + all three `ledger_entries` atomically.
- `ledger_entries` has `UNIQUE(ledger_transaction_id, account)`.
- `ledger_transactions` has `UNIQUE(source_type, source_id)`.
- Both ledger tables are immutable: no update/delete application paths.

### 6.4 Worker ledger behavior

The API computes the bill breakdown once. The worker writes what the event says. The worker must not rederive fee/tax math from current config or plan price. Math drift is a bug.

Paid subscriptions and gifts create ledger transactions. Free subscriptions and tier changes do not create ledger transactions in Phase 1.

---

## 7. Event rules

- `docs/event-catalog.md` is the exclusive event contract.
- Do not invent event names.
- Do not invent payload fields.
- Do not inline post bodies in events.
- All events use the standard envelope.
- Every event carries `correlation_id`.
- Worker-emitted events carry `causation_id`.
- Worker handlers dispatch on `(event_type, event_version)`.
- Every handler dedupes by `event_id`.
- Event handlers must be safe to run twice.

Phase-1 event names:

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

Kernel/meta:

- `ledger.transaction.recorded`
- `event.processing.failed`

Do not use the old name `ledger.entry.created`. It was replaced because the event is one per balanced transaction, not one per ledger row.

---

## 8. Database rules

- Use Alembic for every schema change.
- UUID v4 primary keys.
- Index all foreign keys and common query paths.
- Enforce invariants in the schema where possible.
- No destructive migration without explicit user approval.
- Redis is never source of truth.
- `ledger_transactions`, `ledger_entries`, `post_versions`, and `reconciliation_log` are immutable through application paths.

Required important constraints:

- `users.cognito_sub` unique.
- `publications.handle` unique.
- `idempotency_keys UNIQUE(user_id, key)`.
- `subscriptions` partial unique active subscriber/publication constraint.
- `publication_daily_stats UNIQUE(publication_id, stat_date)`.
- `ledger_transactions UNIQUE(source_type, source_id)`.
- `ledger_entries UNIQUE(ledger_transaction_id, account)`.
- `user_feed_events` indexed by `(user_id, created_at)`.

---

## 9. Backend rules

- Python 3.12+.
- FastAPI.
- Pydantic v2.
- SQLAlchemy 2.x.
- Alembic.
- uv.
- Ruff.
- Pyright or mypy.
- Explicit type hints.
- PEP 8/PEP 484 discipline.
- Business logic belongs in services/domain modules, not route handlers.
- AWS SDK calls belong in integration adapters, never route handlers.
- API responses use typed schemas and validate against OpenAPI.
- Errors use RFC 7807 Problem Details with `correlation_id`.
- `correlation_id` is generated at request entry and propagated to logs/events.

### Schema generation

- `docs/openapi.yaml` is source of truth for API schemas.
- Generated schemas live under `apps/api/app/schemas/generated/`.
- Do not hand-edit generated files.
- Handwritten domain models live separately.
- CI must fail if generated schemas drift from `docs/openapi.yaml`.

---

## 10. Frontend rules

- Next.js.
- React.
- TypeScript.
- Tailwind.
- Generated typed API client from `docs/openapi.yaml`.
- Do not duplicate backend domain logic in frontend.
- Make UI states explicit: loading, empty, success, error.
- Prioritize screenshot-readability over flashy UI.
- Dashboard must show subscriber/revenue/feed updates through SSE.

---

## 11. Testing rules

Tests verify behavior, not implementation internals.

### Allowed

- HTTP API tests against OpenAPI behavior.
- DB assertions after public actions.
- Event-handler tests using catalog-valid payloads.
- State-machine tests against legal transitions and observable effects.
- Invariant/property-style tests for ledger and idempotency.
- Fixture builders under `tests/fixtures` or `tests/factories`.

### Forbidden

- Mocking internal service methods to prove behavior.
- Asserting private attributes.
- Asserting internal call order.
- Testing route-handler internals instead of API behavior.
- Importing production-only internals just to make brittle assertions.

### Required verification families

Run the relevant subset for each task:

Backend:

```bash
cd apps/api
uv run ruff check
uv run pyright   # or mypy if configured
uv run pytest
```

Worker:

```bash
cd apps/worker
uv run ruff check
uv run pyright   # or mypy if configured
uv run pytest
```

Frontend:

```bash
cd apps/web
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Infra:

```bash
cd infra/terraform/environments/dev
terraform fmt -check
terraform validate
terraform plan   # only when credentials are configured
```

Never claim a task is done without recording command results or failure summaries in `tasks/todo.md`.

---

## 12. Terraform and AWS safety

Allowed without explicit deploy approval:

- `terraform fmt`.
- `terraform validate`.
- `terraform plan` when credentials exist.

Forbidden unless the user explicitly asks in the current session:

- `terraform apply`.
- `terraform destroy`.
- commands that print secrets.
- reading `.env` files.
- writing secrets to files.
- hardcoding AWS credentials.

Infrastructure rules:

- RDS private.
- ElastiCache private.
- S3 private by default.
- Least-privilege IAM.
- ECS tasks use task roles, not static credentials.
- Every resource tagged with project and environment.
- Maintain scale-to-zero teardown and one-command rebuild scripts.

---

## 13. Observability rules

Structured JSON logs include, when available:

- `request_id`
- `correlation_id`
- `user_id`
- `event_id`
- `event_type`
- `route`
- `status_code`

Instrument API and worker paths with OpenTelemetry.

Required metrics include:

- API request count.
- API p50/p95 latency.
- API error rate.
- SQS queue depth.
- DLQ count/depth.
- Worker success/failure count.
- Worker latency.
- Outbox pending count.
- Outbox oldest pending age.
- Redis cache hit/miss.
- `worker_handler_failures_total`.
- `worker_handler_duration_p95`.
- `sqs_age_of_oldest_message`.

Sprint 6 must define the named CloudWatch alarms from the spec.

---

## 14. Operability rules

Admin surface has exactly three recovery verbs:

1. `retry`
2. `amend & retry`
3. `discard`

Rules:

- All admin verbs require `Idempotency-Key`.
- `retry` is safe and requeues/retries without payload mutation.
- `amend & retry` is feature-flag gated off by default.
- `amend & retry` requires reason and typed confirmation `AMEND <event_id>`.
- `discard` requires a reason of at least 10 characters.
- Every admin action writes immutable `reconciliation_log` row.
- Discarding opens a reconciliation review against the source business row.
- No silent operator fixes.

---

## 15. Security rules

- Validate Cognito JWTs in production: signature, issuer, audience, expiration, token use.
- Local auth shortcut must live in a separate router gated by `ENVIRONMENT=local`.
- Local auth route must not exist in production route surface.
- Never read or print `.env` files unless explicitly asked.
- Never commit secrets.
- Never hardcode credentials.
- Enforce no self-subscribe.
- Enforce no self-gift.
- Enforce owner-only publication/post mutations.
- Enforce subscriber-only access to paid posts.
- Enforce admin-only operability endpoints.

---

## 16. Claude Code workflow

For every non-trivial task:

1. Read this file.
2. Read `tasks/todo.md`.
3. Confirm the active sprint and specific task.
4. Trace the task to OpenAPI/event/architecture/state/ADR/sprint-plan/test-plan.
5. State assumptions before implementation.
6. Write or update `tasks/todo.md` before coding.
7. Make the smallest change that satisfies the task.
8. Do not refactor unrelated code.
9. Do not add speculative abstractions.
10. Run relevant verification commands.
11. Record outputs or failure summaries in `tasks/todo.md`.
12. Add/update ADR if an architectural decision changes.
13. If the user corrects you, add a dated `tasks/lessons.md` entry with: correction, root cause, prevention rule, applied yes/no.

### Task entry format

Each non-trivial task in `tasks/todo.md` should include:

```markdown
## Sx-Tyy — Title

Trace:
- OpenAPI:
- Event:
- Architecture/Data model:
- Sprint plan:
- Test plan:

Assumptions:
- ...

Expected behavior:
- ...

Implementation notes:
- ...

Tests:
- ...

Verification commands:
- ...

Result:
- Pending / passed / failed with notes
```

---

## 17. Style rules

- Simplicity first.
- Surgical changes only.
- No unrelated formatting churn.
- No massive files when small modules suffice.
- Match existing style.
- Remove only dead imports/variables your own change created.
- If you notice unrelated dead code, mention it; do not delete it.
- Every changed line must trace to the active task.
- Prefer boring, readable, production-shaped code.

---

## 18. Sprint and task tracking

- `tasks/todo.md` holds active sprint tasks.
- `tasks/lessons.md` records user corrections and prevention rules.
- `tasks/sprint-review.md` captures end-of-sprint review.
- Do not begin a sprint before the prior sprint's done criteria are met.
- Before starting a new sprint, confirm previous sprint review has: review, evidence, known issues, and next-sprint gate.
- Each sprint must produce a portfolio artifact.

---

## 19. Done criteria

A task is done only when:

- It traces to the sprint plan.
- It matches the spec and contract.
- Scope did not expand.
- Tests/checks ran.
- Results are recorded in `tasks/todo.md`.
- Failures are fixed or explicitly documented.
- No unrelated files changed.
- No secrets were exposed.

A sprint is done only when:

- All sprint tasks are checked.
- `tasks/sprint-review.md` has review/evidence/known issues.
- Lessons are captured.
- Portfolio artifact exists.
- Next sprint is planned.

The project is portfolio-ready only when:

- Cloud deployment works.
- Phase 1 acceptance flow works end-to-end.
- Observability screenshots exist.
- Load-test report exists.
- README explains system design.
- Failure modes are documented.
- Architecture diagram is included.
- Demo screenshots/video exist.

---

## 20. Hard stop conditions

Stop immediately and surface the issue if:

- The task is not traceable to spec/contract/event/architecture/sprint/test artifacts.
- An artifact conflict changes implementation behavior.
- A requested feature is out of Phase 1 scope.
- A migration would be destructive.
- You need to run `terraform apply` or `terraform destroy`.
- You need to read `.env` or any secret file.
- You are about to write money logic with floats.
- You are about to add a new event or event field not in the event catalog.
- You are about to add an endpoint not in OpenAPI.
- You are about to put business logic in a route handler.
- You are about to write ledger rows from the API service.

The correct default is not “add one more helpful thing.” The correct default is **no**.
