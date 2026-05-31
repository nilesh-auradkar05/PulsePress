# PulsePress Task Board

Active sprint: **Sprint 2 — Schema + Auth (+ local integration test + README)**

> Sprint 0 + Sprint 1 complete and merged to `main`. Sprint 2 runs on `sprint-2-schema-auth`.

## Current tasks

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
