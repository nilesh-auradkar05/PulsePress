# Sprint Reviews

## Sprint 0 — Guardrails

Status: **Complete.**

### Review

Stood up the Claude Code control plane on top of the already-complete design pack. No
application code was written. Delivered the two canonical tasks:

- **S0-T01 Normalize repository docs** — verified the existing design pack (OpenAPI parses,
  all local markdown links resolve), fixed a self-contradictory clause in `CLAUDE.md`, added
  `local-dev.md` / `deployment.md` / `observability.md` stubs, and made `.gitignore` cover
  agent-runtime and import-scratch artifacts so they can never be committed.
- **S0-T02 Add safety hooks and commands** — added a PreToolUse safety guard
  (`scripts/hooks/pretool_guard.py`) + a non-blocking Stop reminder
  (`scripts/hooks/stop_verify.py`), wired them in `.claude/settings.json` with a defensive
  `permissions.deny` layer, authored six slash commands, and added three CI verification scripts.

### Evidence

- `python3 scripts/ci/test_agent_hooks.py` → **18/18 guard cases pass** (`.env`/secret reads,
  `terraform apply|destroy`, `cat/source .env`, `printenv`, `rm -rf /`, force-push to main all
  blocked; `terraform validate|fmt|plan` and benign commands allowed).
- `python3 scripts/ci/validate_openapi.py docs/openapi.yaml` → OpenAPI 3.1.0, 21 paths, all with ≥1 operation.
- `python3 scripts/ci/check_docs_links.py docs CLAUDE.md README.md` → all local links resolve across 39 files.
- `git check-ignore` confirms `node_modules`, `data`, `package.json`, `package-lock.json`,
  `old_files`, `original_design_html`, `pulsepress_revised_spec_pack_v1_3`, `MANIFEST.txt` are ignored.
- Full command outputs recorded in `tasks/todo.md` Evidence log.

### Known issues

- `validate_openapi.py` does full validation only when PyYAML is importable (present here); it
  degrades to a structural line-scan otherwise. Acceptable for Sprint 0 — revisit in CI (Sprint 1+).
- The guard is advisory/heuristic (fails open on malformed input); `permissions.deny` is the
  hard backstop for `.env` reads and `terraform apply|destroy`.
- Root `README.md` still carries spec-pack placeholder text (full rewrite is Sprint 8 scope).

### Next sprint gate

Sprint 1 — Foundation + walking-skeleton deploy (S1-T01 monorepo skeleton: `apps/api`,
`apps/worker`, `apps/web`, `infra/terraform`; then FastAPI `/healthz` deployed to ECS Fargate).
Gate satisfied: Sprint 0 tasks checked, evidence recorded, lessons captured.

### Portfolio artifact

The committable control plane itself: hooks + guard + slash commands + CI verification scripts
demonstrating disciplined, spec-driven agent operation before any feature code.

---

## Sprint 1 — Foundation + walking-skeleton deploy

Status: **Complete (build-only).**

### Review

Established the monorepo (`docs/SPEC.md` §15) and the walking-skeleton deploy artifact. Per the
confirmed sprint decisions this was **build-only** — no `terraform apply`, no AWS resources created.

- **S1-T01 Monorepo skeleton** — `apps/api` (FastAPI + uv), `apps/worker` (uv skeleton),
  `apps/web` (Next.js + TS + Tailwind), `infra/terraform`, plus `docker-compose.yml` and
  `scripts/dev/{up,down}.sh`. Each app passes its own lint/typecheck/test-or-build. Only the
  subpackages `/healthz` needs were created under `apps/api/app/`; the rest of the §15 tree is
  added in the sprint that needs it.
- **S1-T02 FastAPI `/healthz`** — internal operability endpoint (no auth, static JSON), kept out of
  the product OpenAPI contract by design (sanctioned by S1-T02 trace; see lessons 2026-05-30).
  Verified by a behavioral test and a real container healthcheck + `curl`.
- **S1-T03 Terraform foundation** — `network` (VPC, public/private subnets, IGW, no NAT), `ecr`
  (api + worker repos), `alb` (HTTP:80, `/healthz` health check), `ecs` (cluster + API Fargate
  service in public subnets, least-privilege SG, IAM roles, CloudWatch log group). `fmt`/`init`/
  `validate` clean. ADR-0006 filled.
- **S1-CI** — `.github/workflows/ci.yml`: api/worker/web/terraform/guardrails jobs (no deploy
  stage). Folds the Sprint 0 guardrail scripts into CI, closing that Sprint 0 known issue.

### Evidence

See `tasks/todo.md` Evidence log for full outputs. Summary: api ruff/pyright/pytest (2/2) green;
worker ruff/pyright/pytest (1/1) green; web lint/typecheck/`next build` green; docker-compose API
container `healthy` and `/healthz` → `{"service":"pulsepress-api","version":"0.1.0","status":"ok"}`;
terraform 1.9.8 `fmt -check`/`init -backend=false`/`validate` all clean; guardrail scripts 3/3 pass.

### Known issues

- **Build-only:** the skeleton is not yet deployed to AWS. `terraform apply` is a separate,
  user-approved step; CI verifies but never applies.
- **Public-subnet Fargate / HTTP-only ALB / no NAT** — deliberate `$0`-at-rest tradeoff
  (ADR-0006/0007). Revisit TLS/ACM + private networking when product endpoints and RDS/Redis land.
- Local toolchain gaps: `terraform` and `pnpm` were fetched/installed ad hoc (not pre-provisioned);
  `pyright` ran via `uv`. CI provisions all of them deterministically.
- Root `README.md` still carries spec-pack placeholder text (full rewrite is Sprint 8 scope).

### Next sprint gate

Sprint 2 — Schema + auth (S2-T01 Alembic 17-table base schema; S2-T02 Cognito JWT validation +
`/me`; S2-T03 RDS + ElastiCache Terraform in the private subnets reserved this sprint). Gate
satisfied: Sprint 1 tasks checked, evidence recorded, lessons captured, ADR-0006 filled.

### Portfolio artifact

A deployable walking skeleton: a clean monorepo, a `/healthz` FastAPI service, and Terraform that
provisions VPC → ECR → ALB → ECS Fargate — all `validate`-clean and CI-gated, demonstrating
"deploy a tiny slice first" (ADR-0006) before any feature code.

---

## Sprint 2 — Schema + auth (+ local integration test + README)

Status: **Complete (build-only cloud).**

### Review

Delivered the data + auth foundation and a working local stack, plus two user-directed additions.

- **S2-T01 Schema** — SQLAlchemy 2.x models for all **17** Phase-1 tables + Alembic initial
  migration. Constraints enforced in-schema: `cognito_sub`/`handle` unique, `idempotency_keys`
  UQ(user,key), the **partial-unique active subscription** index, `publication_daily_stats`
  UQ(pub,date), the two **`ledger_transactions` balance CHECKs** + UQ(source), `ledger_entries`
  UQ(tx,account). Append-only tables (`ledger_transactions`, `ledger_entries`, `post_versions`,
  `reconciliation_log`) protected by a SQLAlchemy immutability guard. ADR-0012 filled.
- **S2-T02 Auth** — production Cognito RS256/JWKS verification (issuer/audience/exp/token_use), a
  `ENVIRONMENT=local` dev-auth shortcut (HS256, separate router, not in the OpenAPI contract),
  `GET /v1/me`, an `X-Correlation-Id` middleware, and RFC 7807 error responses. ADR-0002 filled.
- **S2-T03 Terraform** — `rds` (private Postgres, managed password in Secrets Manager),
  `elasticache` (private Redis), `cognito` (user pool + PKCE app client); service SG lifted to the
  env to avoid a dependency cycle; secrets passed as references. Build-only.
- **S2-T04 (user) Local stack + functional test** — docker-compose (db + redis + migrate + api +
  web standalone image), frontend auth wiring (`lib/api.ts`, real `AuthProvider`, wired
  login/register with error states), `scripts/dev/migrate.sh`, filled `docs/local-dev.md`, and a
  Postgres service added to the CI backend job. Verified end-to-end with curl + the web container.
- **S2-T05 (user) README** — full 5-section README (name + spec-driven/agentic-AI note, description/
  motivation/goal, setup & testing, features ✅/⬜, sprints ✅/⬜).

### Evidence

See `tasks/todo.md` Evidence log. Highlights: backend **23 tests pass** (ruff/pyright clean) against
real Postgres; migration upgrade/downgrade roundtrip; terraform `fmt`/`init`/`validate` clean across
7 modules; `docker compose up` → register → `/v1/me` → login all succeed and `/v1/me` is 401 without
a token; web standalone image serves `/`, `/login`, `/register`.

### Known issues

- **Build-only cloud:** RDS/Redis/Cognito + ECS are authored and `validate`-clean but **not applied**;
  no AWS resources exist yet.
- **Local auth only:** the browser uses the dev-auth shortcut; the real Cognito hosted-UI + PKCE flow
  is deferred (Sprint 5/8). The frontend Home feed is still mock data (posts API is Sprint 3).
- Host port 3000 was occupied on the dev machine; the web container was verified on 3001 (compose
  maps the standard 3000).
- DB-backed tests require Postgres (`TEST_DATABASE_URL`); they skip cleanly when it is unset.

### Next sprint gate

Sprint 3 — Commerce API + outbox (publication/plan CRUD; subscribe/tier-change/cancel/gift with
idempotency; transactional outbox; bill breakdown). Gate satisfied: Sprint 2 tasks checked, evidence
recorded, lessons captured, ADR-0002 + ADR-0012 filled.

### Portfolio artifact

A runnable local platform: `scripts/dev/up.sh` brings up Postgres + Redis + a migrated 17-table
schema + the auth API + the Next.js frontend, and a user can register / sign in end to end — backed
by a balance-checked, immutable ledger schema and rigorous (local + Cognito) JWT validation.
