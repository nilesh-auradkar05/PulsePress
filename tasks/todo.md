# PulsePress Task Board

Active sprint: **Sprint 5 — Publishing + Newsletter + SSE (not started)**

> Sprint 0/1/2 complete and merged to `origin/main` (PR #3). Sprint 3 runs on
> `sprint-3-commerce-outbox` (branched off `origin/main`). Sprint 3 is complete;
> Sprint 4 is complete: it activates commerce delivery locally and validates
> the AWS Terraform wiring. Sprint 5 will route the pending publishing events.

## Completed tasks (Sprint 4)

- [x] S4-T01 — Transactional outbox poller with SKIP LOCKED, EventBridge delivery, backoff, and terminal failed rows
- [x] S4-T02 — Worker claims/idempotency, source validation, create-only receipts, and SQS delete-after-success
- [x] S4-T03 — Subscription handler with stable charge snapshot and DB-enforced three-entry ledger
- [x] S4-T04 — Gift handler with ledger, receipt, stats, and duplicate safety
- [x] S4-T05 — Separate EventBridge and worker DLQs; one terminal failure signal; least-privilege worker IAM

Evidence: API `87 passed`; worker `20 passed`; API/worker ruff and pyright clean;
Terraform fmt/validate clean. No AWS apply was performed.

---

## S3 — Commerce API + Outbox

Trace: OpenAPI `listPlans`/`createPlan`/`createSubscription`/`changeTier`/`cancelSubscription`/
`sendGift`/`getSubscription`; Events `subscription.created`/`subscription.tier_changed`/
`subscription.canceled`/`gift.sent`; ER `subscription_plans`/`subscriptions`/`gift_transactions`/
`idempotency_keys`/`outbox_events`; CLAUDE.md §5.1/§6/§9; SPEC §7; sprint-plan S3-T01…T07; test-plan §2/§4.

Scope:
- Service layer `app/services/` (CLAUDE.md §9): `idempotency`, `outbox`, `commerce`, `errors`;
  pure money in `app/domain/money.py`; `app/schemas/commerce.py`; config `platform_fee_pct`/`tax_pct`.
- Routers `app/api/{plans,subscriptions,gifts}.py` — thin; money-shaped writes require `Idempotency-Key`
  and atomically write business row + idempotency record + outbox event; **no ledger in the API**.
- Bill computed once (integer cents, round-half-up, author_net residual); carried in event payload.
- Outbox rows carry the full envelope (incl. `correlation_id`) in `payload`; `publishPost` retrofitted.

Expected behavior: paid subscribe → 201 + bill + 1 `subscription.created` outbox row, **no ledger**;
free subscribe → bill null, still emits + idempotent; self-subscribe 403; duplicate active 409;
missing key 422; same key+body replay (`Idempotency-Replayed: true`); same key+diff body 422;
tier change 200 + event; cancel retains access + emits once, repeat is 200 no-op; gift 201 + bill +
`gift.sent`, self-gift 403, < 50c 422.

Result: **passed** (see Sprint 3 Evidence log)

---

## Sprint 3 Evidence log

### Backend (apps/api) — ruff / pyright / pytest (Postgres :5432/pulsepress_test)
```
uv run ruff check    -> All checks passed!
uv run pyright       -> 0 errors, 0 warnings, 0 informations
uv run pytest -q     -> 77 passed   (23 prior + 54 new: 7 money, 5 plans, ~13 subscriptions, 5 gifts, …)
```
- `compute_bill` matches the event-catalog examples (500→fee 50/tax 40/net 450/total 540;
  1000→fee 100/tax 80/net 900/total 1080); round-half-up + balance invariants property-tested;
  a source guard asserts no floats in the money module.
- Outbox atomicity: each commerce write produces exactly one envelope-wrapped `outbox_events` row
  with a `correlation_id`; **zero `ledger_transactions`** written by the API (worker is Sprint 4).
- Idempotency: replay returns the stored body + `Idempotency-Replayed: true`; same key + different
  body → 422; a failed request caches nothing (its idempotency row rolls back with the txn).

### Contract / docs / app
```
scripts/ci/validate_openapi.py docs/openapi.yaml  -> OK (3.1.0, 21 paths)   [contract unchanged]
scripts/ci/check_docs_links.py docs CLAUDE.md README.md -> OK (41 files)
create_app() mounts /v1/publications/{id}/plans, /v1/subscriptions[/{id}], /v1/gifts
```

Branch hygiene: `sprint-3-commerce-outbox` was branched off `origin/main` (the Sprint-2 + content-MVP
integration). Pending (not part of the Sprint-3 code commit): `docs/aws-production-setup-guide.md`,
the renamed/reorganized `docs/setup-test-guide.md` (cumulative per-sprint setup+test guide, replaces
`docs/sprint-2-setup-test-guide.md`), and the matching `.gitignore` whitelist update.

---

## Worker hardening — post-review bug-fix log (2026-06-21)

Two HIGH correctness bugs were found by a multi-agent review of the (uncommitted, Sprint-4)
worker and fixed via subagent-driven development. Working-tree only — commit handled manually.

**Bug 1 — false-terminal accounting** (`apps/worker/pulsepress_worker/processor.py`).
- *What:* terminal classification was `receive_count >= max OR attempt_number >= max`.
  `receive_count` is SQS `ApproximateReceiveCount`, which inflates on lease contention
  (`EventInProgressError` re-raises before `attempt_number` is incremented).
- *Why it mattered:* a single genuine failure (`attempt_number == 1`) could be marked
  terminal purely from SQS receive-count inflation — setting `terminal_at` and emitting
  `event.processing.failed`, permanently abandoning a recoverable event.
- *How resolved:* terminal is now driven solely by the durable `claim.attempt_number`
  (`terminal = claim.attempt_number >= self._max_event_attempts`). The now-unused
  `receive_count` parameter was removed from `process_mapping`/`_process` and the
  `queue.py` call site; `QueueMessage.receive_count` (SQS metadata) retained.

**Bug 2 — orphaned "started" lease / receipt written outside the handler transaction**
(`processor.py`).
- *What:* the durable receipt PUT happens before the handler DB transaction; a hard crash
  in that gap leaves the attempt `status="started"` with a live lease and no ledger row.
- *Why it mattered:* the event stalls until the lease expires; needed proof it self-heals
  without double durable effects, plus a documented contract.
- *How resolved:* no structural change (moving the S3 PUT under the row lock would deadlock
  the concurrency test; S3↔Postgres atomicity is impossible — the lease IS the intended
  crash recovery). Added an at-least-once recovery comment at the receipt-write site, and
  regression tests: `test_crash_between_receipt_and_ledger_commit_self_heals` (receipt
  idempotency + clean recovery), `test_same_event_id_ledger_dedup_on_reclaim` (genuinely
  exercises `_write_ledger`'s same-event `return False` dedup branch), and
  `test_duplicate_claim_writes_no_receipt`.

**Verification (live Postgres):** worker `ruff` clean · `pyright` 0/0/0 · `pytest` 24 passed
(was 20: +2 bug-fix regressions, +2 review-hardening tests); api `pytest` 87 passed.
Files changed: `processor.py`, `queue.py`, `tests/test_processor.py`.

---

## Sprint 2 (complete — merged to `origin/main`)

- [x] S2-T01 — Alembic 17-table base schema (models, constraints, immutability, tests)
- [x] S2-T02 — Cognito JWT validation + local-dev auth router + `/me` (+ correlation middleware)
- [x] S2-T03 — RDS + ElastiCache + Cognito Terraform (build-only)
- [x] S2-T04 — Local dev stack + DB schema steps + frontend functional test (user-added)
- [x] S2-T05 — README.md rewrite, 5-section structure (user-added)

---

## S2-T01 — Alembic 17-table base schema

Trace: architecture §5/§6, SPEC §6 (17 tables), CLAUDE.md §6/§8, test-plan §4; ADR-0012.

Scope:
- SQLAlchemy 2.x typed models for all 17 Phase-1 tables, UUID v4 PKs, FK indexes, audit timestamps.
- Constraints: users.cognito_sub UQ; publications.handle UQ; idempotency_keys UQ(user_id,key);
  subscriptions partial-unique active; publication_daily_stats UQ(publication_id,stat_date);
  ledger_transactions UQ(source_type,source_id) + 2 CHECKs; ledger_entries UQ(tx,account);
  user_feed_events index(user_id,created_at).
- Immutability guard (SQLAlchemy event) on ledger_transactions/ledger_entries/post_versions/reconciliation_log.
- Alembic env + 0001_initial migration (all tables/constraints/indexes).

Tests: migration upgrade↓downgrade; constraint rejections; immutable update/delete raises.

Verification: `cd apps/api && uv run ruff check && uv run pyright && uv run pytest` (against test Postgres).

Result: **passed** (see Evidence log)

---

## S2-T02 — Cognito JWT validation + local-dev auth + `/me`

Trace: OpenAPI `/me` + `bearerAuth`, SPEC §14, CLAUDE.md §15; ADR-0002.

Scope:
- Prod verifier (RS256 via cached JWKS; issuer/audience/exp/token_use).
- Local verifier+minter (HS256, `LOCAL_JWT_SECRET`); local-only router `/local/auth/{register,login}`
  mounted only when `ENVIRONMENT=local` (NOT in OpenAPI).
- `get_current_user` dependency (load/create users row); `GET /v1/me` → `User`.
- `X-Correlation-Id` middleware; RFC7807 Problem responses.
- Fill ADR-0002.

Tests: missing/invalid → 401 Problem (correlation id present); valid local token → 200 User;
local router absent when ENVIRONMENT≠local; prod verifier unit tests (happy/expired/bad-iss/bad-aud).

Result: **passed** (see Evidence log)

---

## S2-T03 — RDS + ElastiCache + Cognito Terraform (build-only)

Trace: SPEC §4/§14, architecture §12, sprint-plan S2-T03.

Scope: modules/rds (private Postgres, SG from service SG, Secrets Manager creds), modules/elasticache
(private Redis), modules/cognito (user pool + PKCE app client); wire into environments/dev; pass
DATABASE_URL/REDIS_URL/COGNITO_* to the API task as secret/SSM references. No committed secrets.

Verification: terraform `fmt -check` + `init -backend=false` + `validate`. No apply.

Result: **passed** (see Evidence log)

---

## S2-T04 — Local dev stack + DB schema + frontend functional test (user-added)

Trace: user-directed; local-dev.md, docker-compose. Goal: prove frontend login/register works
end-to-end and Sprint 2 pieces run locally.

Scope: docker-compose db+redis+migrate+api+web; apps/web Dockerfile (Next standalone); frontend auth
wiring (`lib/api.ts`, AuthProvider real login/register/logout + token + /me, wired forms); scripts/dev
migrate/seed; fill docs/local-dev.md; CI postgres service for the api job.

Verification: docker compose up → healthy; curl register→token, /v1/me→user; web register/login works.

Result: **passed** (see Evidence log)

---

## S2-T05 — README.md (user-specified structure)

Trace: user-directed. Sections: 1) Project name + spec-driven/agentic-AI note; 2) description/
motivation/goal; 3) setup + testing; 4) features (✅/⬜); 5) sprints (✅/⬜). + architecture blurb.

Result: **passed** (see Evidence log)

---

## Evidence log

### Backend (apps/api) — ruff / pyright / pytest (Postgres on :5544/pulsepress_test)
```
uv run ruff check    -> All checks passed!
uv run pyright       -> 0 errors, 0 warnings, 0 informations
uv run pytest -q     -> 23 passed
  (2 health, 6 constraints, 3 immutability, 1 migration roundtrip, 11 auth)
```
Schema: `alembic revision --autogenerate` detected all 17 tables, the partial-unique active-
subscription index, both ledger balance CHECKs, and unique keys. `upgrade head` → 17 tables +
alembic_version; `downgrade base` → 1; re-`upgrade head` → 17. (verified on disposable Postgres)

### Terraform (build-only; terraform 1.9.8)
```
fmt -check -recursive                 -> clean
init -backend=false (modules: network, ecr, alb, ecs, rds, elasticache, cognito) -> initialized
validate                              -> Success! The configuration is valid.
```
Service SG created at env level to avoid an ecs↔rds/redis dependency cycle. DB creds via RDS-managed
Secrets Manager password; app DATABASE_URL via a Secrets Manager container (no committed secrets).

### Local stack + functional test (docker compose: db + redis + migrate + api + web)
```
migrate            -> Running upgrade -> 1d39f6eeaae8, initial schema ; users table present
api /healthz       -> {"service":"pulsepress-api","version":"0.1.0","status":"ok"} ; container healthy
POST /local/auth/register {ada} -> 201 {access_token, user{id, display_name:"Ada Lovelace"}}
GET  /v1/me  (Bearer)           -> 200 same user
POST /local/auth/login {ada}    -> 200 token + user
GET  /v1/me  (no token)         -> 401
web image (Next standalone)     -> built; / , /login , /register all HTTP 200
```
(Host port 3000 was occupied on this machine, so the web container was verified on 3001; compose
maps the standard 3000.)

### Web (apps/web) — lint / typecheck / build
```
pnpm lint       -> ✔ No ESLint warnings or errors
pnpm typecheck  -> tsc --noEmit, no errors
pnpm build      -> ✓ Compiled; routes / , /login , /register (standalone output)
```

### Guardrails (Sprint 0 scripts; also in CI)
```
validate_openapi.py / check_docs_links.py / test_agent_hooks.py -> all pass
```

ADRs filled: ADR-0002 (Cognito + local shortcut), ADR-0012 (ledger_transactions over cross-row CHECK).
