# PulsePress Sprint Plan

**Version:** v1.1  
**Scope:** Phase 1  
**Canonical for:** execution tasks, traces, verification commands, sprint gates.

## Sprint execution rule

Every task must trace to at least one of:

- OpenAPI operationId.
- Event catalog event.
- ER table/model.
- State-machine transition.
- Sequence step.
- ADR.

No trace means no implementation. Yes, this is harsh. So are bugs.

## Task template

```text
Task ID:
Trace:
Goal:
Scope:
Expected behavior:
Tests:
Verification:
Done criteria:
Non-goals:
```

---

# Sprint 0 — Guardrails

Goal: commit design pack, repo skeleton, AI-agent rules, task board, and verification scripts. No app feature code.

## S0-T01 — Normalize repository docs

Trace: SPEC §15, CLAUDE.md  
Goal: establish architecture/execution/enforcement separation.

Scope:

- Add `docs/SPEC.md`.
- Add `docs/architecture.md`.
- Add `docs/openapi.yaml`.
- Add `docs/event-catalog.md`.
- Add `docs/sprint-plan.md`.
- Add `docs/test-plan.md`.
- Add canonical `CLAUDE.md`.
- Add `tasks/todo.md`, `tasks/lessons.md`, `tasks/sprint-review.md`.

Expected behavior:

- New task work starts from `tasks/todo.md`.
- Claude Code rules point to `CLAUDE.md`.
- No duplicate contradictory rules across docs.

Tests:

- Markdown links resolve for all local docs.
- OpenAPI parses.

Verification:

```bash
python scripts/ci/validate_openapi.py docs/openapi.yaml
python scripts/ci/check_docs_links.py docs CLAUDE.md
```

Done criteria:

- All files exist.
- No app code added.
- Sprint review records setup evidence.

## S0-T02 — Add safety hooks and commands

Trace: CLAUDE.md, SPEC §16  
Goal: prevent dangerous or scope-creep operations.

Scope:

- Pre-tool guard blocks `.env` reads, secret printing, `terraform apply`, `terraform destroy`, broad destructive shell commands.
- Stop/verify reminder checks `tasks/todo.md` update.
- Add slash commands: `/plan-sprint`, `/implement-task`, `/verify-task`, `/review-diff`, `/write-adr`, `/prep-portfolio`.

Tests:

- Attempted `.env` read is blocked.
- Attempted `terraform apply` is blocked.
- Safe `terraform validate` is allowed.

Verification:

```bash
python scripts/ci/test_agent_hooks.py
```

Non-goals:

- No production feature code.

---

# Sprint 1 — Foundation + walking-skeleton deploy

Goal: local stack and `/healthz` API deployed to ECS Fargate behind ALB.

## S1-T01 — Create monorepo skeleton

Trace: SPEC §15  
Expected behavior:

- `apps/api`, `apps/worker`, `apps/web`, `infra/terraform`, `scripts`, `docs`, `tasks` exist.
- Python packages use uv.
- Frontend uses pnpm.
- Dockerfiles build minimal services.

Tests:

```bash
uv run ruff check apps/api apps/worker
uv run pyright apps/api apps/worker
pnpm --dir apps/web lint
```

## S1-T02 — FastAPI `/healthz`

Trace: OpenAPI future internal health endpoint, ADR-0006  
Expected behavior:

- `GET /healthz` returns 200 and static JSON.
- No auth required.
- Includes service name, version, and status.

Tests:

- HTTP test returns 200.
- Response schema matches internal health schema.

## S1-T03 — Terraform foundation

Trace: ADR-0001, ADR-0006  
Expected behavior:

- Network module.
- ECS cluster/service skeleton.
- ALB route to API.
- ECR repositories.
- CloudWatch log groups.
- No RDS/Redis yet unless required by service skeleton.

Verification:

```bash
terraform -chdir=infra/terraform/environments/dev fmt -check
terraform -chdir=infra/terraform/environments/dev validate
terraform -chdir=infra/terraform/environments/dev plan
```

Do not run apply unless the user explicitly requests deployment in the current session.

---

# Sprint 2 — Schema + auth

Goal: PostgreSQL schema, Cognito auth, JWT validation, `/me`, RDS + ElastiCache provisioned.

## S2-T01 — Alembic base schema

Trace: Architecture §5, SPEC §6  
Expected behavior:

- Create 17 Phase-1 tables.
- UUID primary keys.
- FK indexes.
- Immutable table protections for `ledger_transactions`, `ledger_entries`, `post_versions`, `reconciliation_log`.
- Partial unique active subscription constraint.
- `ledger_transactions` DB CHECK constraints.

Tests:

- Migration upgrade/downgrade test.
- Constraint tests for duplicate active subscription.
- CHECK constraint rejects unbalanced ledger transaction.
- Immutable tables reject update/delete through repository layer.

## S2-T02 — Cognito JWT validation

Trace: OpenAPI security, SPEC §14  
Expected behavior:

- Production validates signature, issuer, audience, expiration, token use.
- Local dev shortcut exists only under `ENVIRONMENT=local` and separate router.
- `/me` returns `User` schema.

Tests:

- Missing token → 401.
- Invalid token → 401.
- Valid token → 200.
- Local dev route absent outside local.

## S2-T03 — RDS + ElastiCache Terraform

Trace: SPEC §4, §14  
Expected behavior:

- Private RDS.
- Private Redis.
- Security groups least privilege.
- Secrets via SSM/Secrets Manager references, not committed values.

Verification:

```bash
terraform fmt -check
terraform validate
terraform plan
```

---

# Sprint 3 — Commerce API + outbox

Goal: publication/plan CRUD, subscription/gift commerce writes, idempotency, transactional outbox. Events accumulate unprocessed.

## S3-T01 — Publication endpoints

Trace: OpenAPI `listPublications`, `createPublication`, `getPublication`, `updatePublication`, `getPublicationSummary`  
Expected behavior:

- Create/list/detail/update profile fields.
- Owner-only update.
- No event emission.
- Summary reads DB directly until cache added.

Tests:

- Create success.
- Duplicate handle → 409.
- Invalid handle → 422.
- Non-owner update → 403.

## S3-T02 — Plan endpoints

Trace: OpenAPI `listPlans`, `createPlan`; ER `subscription_plans`  
Expected behavior:

- Owner can create free or paid USD plan.
- `allow_open_amount` supports above-floor payment.
- Non-owner cannot create plan.
- Plans are soft-active/inactive only when later added; no delete in Phase 1.

Tests:

- Free plan success.
- Paid plan success.
- Negative price rejected.
- Non-USD rejected.
- Non-owner rejected.

## S3-T03 — Idempotency middleware/service

Trace: ER `idempotency_keys`; OpenAPI IdempotencyKey  
Expected behavior:

- Required on all commerce mutations.
- Same key + same request hash returns stored response.
- Same key + different body returns 422.
- Locks in-flight request to prevent race.

Tests:

- Replay returns original body and `Idempotency-Replayed: true`.
- Conflict returns 422.
- Concurrent same-key requests do not double-write.

## S3-T04 — Create subscription

Trace: OpenAPI `createSubscription`; Event `subscription.created`; ER `subscriptions`, `outbox_events`  
Expected behavior:

- Requires auth and idempotency key.
- Rejects self-subscribe.
- Rejects inactive/missing plan.
- Rejects duplicate active subscription.
- Computes bill once with integer cents.
- Writes subscription + outbox + idempotency record atomically.
- Free plan has `bill=null`, emits event, no ledger yet.
- Paid plan includes bill in response, no ledger until worker.

Tests:

- Paid happy path.
- Free happy path.
- Self-subscribe → 403.
- Duplicate active → 409.
- Same idempotency key/body replay.
- Same key/different body → 422.
- DB atomicity: no subscription without outbox event.

## S3-T05 — Change tier

Trace: OpenAPI `changeTier`; Event `subscription.tier_changed`  
Expected behavior:

- Requires idempotency key.
- Updates `plan_id` and `amount_cents` immediately.
- Emits event.
- No ledger transaction in Phase 1.
- Rejects non-owner? Caller must be subscriber who owns the subscription.

Tests:

- Active subscription tier change success.
- Canceled/expired rejected or no-op according to contract.
- Same key replay.
- Outbox event written atomically.

## S3-T06 — Cancel subscription

Trace: OpenAPI `cancelSubscription`; Event `subscription.canceled`  
Expected behavior:

- Requires idempotency key.
- `active → canceled`.
- Sets `canceled_at` and `access_until=period_end`.
- Emits event only on first successful cancellation.
- Later canceled call returns 200 no-op.

Tests:

- Cancel success.
- Access retained until period end.
- Duplicate key replay.
- Later no-op emits no duplicate event.

## S3-T07 — Send gift

Trace: OpenAPI `sendGift`; Event `gift.sent`; ER `gift_transactions`  
Expected behavior:

- Requires idempotency key.
- Rejects self-gift.
- Rejects amount < 50 cents.
- Computes bill once.
- Writes gift + outbox + idempotency atomically.

Tests:

- Happy path.
- Self-gift → 403.
- Below minimum → 422.
- Idempotency replay/conflict.

---

# Sprint 4 — Worker + ledger

Goal: outbox poller, EventBridge→SQS→worker, idempotent handlers, ledger transactions, receipts, DLQ.

## S4-T01 — Outbox poller

Trace: ADR-0011, ER `outbox_events`  
Expected behavior:

- Uses `FOR UPDATE SKIP LOCKED`.
- Publishes to EventBridge.
- Marks published only after successful publish.
- Failed publish increments attempts and records error.

Tests:

- Multiple pollers do not double-claim row.
- Publish failure leaves row retryable.

## S4-T02 — Worker idempotency

Trace: ER `event_processing_attempts`; Event envelope  
Expected behavior:

- Dedupes by event_id.
- Records started/succeeded/failed attempts.
- Deletes SQS message only after success.

Tests:

- Same event twice writes durable state once.
- Failed handler records failure.

## S4-T03 — Subscription ledger handler

Trace: Event `subscription.created`; ER `ledger_transactions`, `ledger_entries`  
Expected behavior:

- Free subscription updates stats but writes no ledger.
- Paid subscription writes one ledger transaction plus three entries.
- Emits `ledger.transaction.recorded`.
- Stores simulated receipt artifact in S3.

Tests:

- Three entries exactly.
- Ledger transaction CHECK passes.
- Duplicate event does not duplicate ledger.

## S4-T04 — Gift ledger handler

Trace: Event `gift.sent`  
Expected behavior:

- Writes one ledger transaction plus three entries.
- Updates gift status processed.
- Emits `ledger.transaction.recorded`.
- Stores receipt artifact in S3.

Tests:

- Happy path.
- S3 failure behavior documented and tested.
- Duplicate event safe.

## S4-T05 — DLQ and failure event

Trace: Event `event.processing.failed`, SPEC §12  
Expected behavior:

- Poison messages surface in DLQ/admin view.
- Worker emits/records failure signal.
- Source business row is not silently mutated.

Tests:

- Poison event reaches failed state.
- Admin list can see it later.

---

# Sprint 5 — Publishing + newsletter + SSE

Goal: post CRUD, publish event-door, newsletter simulation, Redis pub/sub, SSE, post gating.

## S5-T01 — Post CRUD and gating

Trace: OpenAPI posts; State machine `draft → published → archived`  
Expected behavior:

- Owner can create/edit/archive posts.
- Editing published post emits no event.
- Paid post body withheld from unauthorized readers.
- Archived post invisible to readers.

Tests:

- Owner sees drafts and paid posts.
- Non-subscriber sees paid metadata without body.
- Paid subscriber sees body.

## S5-T02 — Publish post

Trace: OpenAPI `publishPost`; Event `post.published`; ER `post_versions`  
Expected behavior:

- Draft publishes once.
- Writes immutable snapshot.
- Writes outbox event atomically.
- Re-publish returns 200 no-op with same version_id.

Tests:

- First publish creates snapshot + outbox.
- Second publish creates no duplicate event.
- Archived post cannot publish.

## S5-T03 — Newsletter worker

Trace: Events `post.published`, `newsletter.send.requested`, `newsletter.sent`, `newsletter.send.failed`  
Expected behavior:

- Renders from snapshot.
- Stores S3 artifact.
- Snapshots recipients.
- Writes `user_feed_events`.
- Updates `newsletter_sends`.

Tests:

- Free post fanout all active subscribers.
- Paid post fanout paid active/canceled-with-access only.
- Expired excluded.
- Post edit after publish does not change artifact.

## S5-T04 — Redis + SSE

Trace: OpenAPI feed endpoints; ADR-0004/0005  
Expected behavior:

- Redis pub/sub broadcasts dashboard/feed events.
- Durable DB read model backs reload/reconnect.
- Redis outage degrades live stream but does not corrupt DB state.

Tests:

- SSE receives event.
- Recent events endpoint returns durable DB events.
- Redis unavailable returns graceful error/degraded behavior.

---

# Sprint 6 — Operability

Goal: CloudWatch alarms, admin runbook verbs, reconciliation, chaos scripts.

## S6-T01 — Admin list endpoints

Trace: OpenAPI admin list operations  
Expected behavior:

- Admin only.
- List outbox events, worker attempts, reconciliation reviews.
- Supports status filters and pagination where defined.

Tests:

- Non-admin → 403.
- Admin → 200.

## S6-T02 — Retry

Trace: OpenAPI `retryOutboxEvent`; Operability layer  
Expected behavior:

- Requires idempotency key and reason.
- Resets eligible failed/discarded? event to pending according to runbook.
- Writes reconciliation log.

Tests:

- Retry writes audit row.
- Duplicate key replay safe.

## S6-T03 — Amend & retry

Trace: OpenAPI `amendOutboxEvent`  
Expected behavior:

- Feature flag off by default.
- Requires reason and `AMEND <event_id>` confirmation.
- Creates new outbox event.
- Marks original superseded.
- Writes reconciliation log.

Tests:

- Disabled → 403.
- Bad signature → 422.
- Enabled happy path.

## S6-T04 — Discard

Trace: OpenAPI `discardOutboxEvent`  
Expected behavior:

- Requires idempotency key and reason >= 10 chars.
- Marks event discarded.
- Opens reconciliation review.
- Emits ops alert signal.

Tests:

- Reason too short → 422.
- Discard creates reconciliation review.

## S6-T05 — CloudWatch alarms + chaos scripts

Trace: SPEC §12/§13  
Expected behavior:

- Define five alarms.
- Chaos script can poison event and break worker.
- Evidence captured in sprint review.

Verification:

```bash
terraform fmt -check
terraform validate
pytest apps/worker/tests/test_failure_modes.py
```

---

# Sprint 7 — Hardening + load

Goal: load test, failure-mode proof, DB tuning, scale-to-zero verification.

Tasks:

- S7-T01 k6 subscribe/gift/publish load test.
- S7-T02 p95 and error-rate report.
- S7-T03 DB index review using slow query logs or EXPLAIN.
- S7-T04 failure mode documentation with screenshots/log excerpts.
- S7-T05 scale-to-zero teardown and one-command rebuild verification.

Verification:

```bash
k6 run scripts/load/phase1_acceptance.js
python scripts/ci/check_cost_tags.py infra/terraform
```

---

# Sprint 8 — Polish + portfolio

Goal: make the project legible to reviewers.

Tasks:

- S8-T01 README architecture and local/cloud runbooks.
- S8-T02 architecture diagram export.
- S8-T03 demo recording checklist.
- S8-T04 resume bullets.
- S8-T05 Phase-2 entry criteria review.
- S8-T06 fresh-clone test.
- S8-T07 fill ADRs.

Done criteria:

- Cloud acceptance flow works.
- README explains design and failure handling.
- Load-test report exists.
- Observability screenshots exist.
- Demo recording or GIF exists.
- Fresh clone can start local dev.
