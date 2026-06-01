# PulsePress

> A cloud-deployed, event-driven **publishing & subscription platform** (a Substack-style model):
> writers run publications, publish posts, and earn through paid subscriptions and one-time gifts,
> all processed through an event-driven backend with a transparent money split and a real
> operability layer.

> 🤖 **This is a spec-driven, agentic-AI–assisted project.** It is built with **Claude Code** as the
> coding agent, governed by a canonical spec pack (`docs/`) and an agent operating manual
> (`CLAUDE.md`). Every change traces to an artifact — an OpenAPI operation, a catalog event, an ER
> table, a state transition, or an ADR — and the agent is constrained by pre-tool guardrails,
> per-sprint task boards (`tasks/`), and verification gates. Nothing is "vibe-coded."

---

## 1. What it is

PulsePress is a portfolio-grade backend/cloud system. It is **publication-centric** (authors set
their own per-publication prices; the platform takes a cut of each payment) and built around one
core idea: **two write-shapes on one event backbone.**

- **Commerce writes** (subscribe, change tier, cancel, gift) are *money-shaped*: idempotency keys, a
  transactional outbox, and an immutable multi-entry ledger.
- **Publishing writes** (create/edit/draft/archive) are *content-shaped*: plain authenticated CRUD.
- The single seam between them is **`publish()`**, the only publishing action that emits an event
  (`post.published`) and triggers newsletter fanout.

## 2. Description, motivation & goal

**Description.** FastAPI API + Python worker on ECS Fargate, PostgreSQL (RDS), Redis (ElastiCache),
SQS + DLQ, EventBridge, S3, and Cognito auth — provisioned with Terraform, shipped via GitHub
Actions, observed with CloudWatch + OpenTelemetry. A transparent three-way bill (author / platform /
tax) is recorded in a balanced ledger; a full operability surface (retry / amend / discard +
reconciliation) recovers failed event processing.

**Motivation.** To demonstrate production-shaped distributed-systems engineering end to end:
idempotency, the transactional-outbox pattern, an event-driven async backbone, a correct
double-entry-style ledger, and real failure handling — not a toy CRUD app. It doubles as a study in
**disciplined, spec-driven AI-assisted development**.

**Goal (Phase 1).** A deployed MVP where a user logs in, creates a publication and tiers, publishes a
post (snapshot + event → worker renders a newsletter to S3 + per-subscriber feed), a second user
subscribes to a paid tier idempotently, the worker writes one balanced ledger transaction + three
entries, a live dashboard updates over SSE, and an operator can recover a deliberately failed event —
all observable in CloudWatch. Medium-style engagement/discovery is **Phase 2 (deferred)**; real
payments are **Phase 3 (out of scope)**.

## 3. Setup & testing

Full guide: **`docs/local-dev.md`**. Quickstart:

**Prerequisites:** Docker, Python 3.12 + `uv`, Node 20 + `pnpm 9`, Terraform 1.6+.

```bash
# 1. Start the whole local stack (Postgres + Redis + migrations + API + web)
scripts/dev/up.sh
#    API  -> http://localhost:8000   (/healthz, /v1/me, local /local/auth/*)
#    web  -> http://localhost:3000

# 2. Database schema (Alembic) — applied automatically by the `migrate` service; or manually:
scripts/dev/migrate.sh                     # docker compose run --rm migrate

# 3. Functional test — prove auth + frontend work end to end
TOKEN=$(curl -fsS -X POST localhost:8000/local/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com","display_name":"Ada Lovelace"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -fsS localhost:8000/v1/me -H "Authorization: Bearer $TOKEN"     # -> the user
#    Then open http://localhost:3000 and register / sign in — the header greets you by name.

# 4. Stop
scripts/dev/down.sh        # add -v to also drop the DB volume
```

**Test suites**

```bash
# Backend (needs Postgres; TEST_DATABASE_URL points at a disposable DB)
cd apps/api && export TEST_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress_test
uv run ruff check && uv run pyright && uv run pytest

# Frontend
pnpm --dir apps/web lint && pnpm --dir apps/web typecheck && pnpm --dir apps/web build

# Infra (build-only — never apply locally)
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform/environments/dev init -backend=false
terraform -chdir=infra/terraform/environments/dev validate
```

CI (`.github/workflows/ci.yml`) runs all of the above on every push/PR (with a Postgres service for
the backend), plus the Sprint 0 guardrail scripts. **Cloud is build-only so far:** Terraform is
authored and validated but not yet applied (no AWS resources created).

## 4. Features

Legend: ✅ complete · 🟡 partial · ⬜ not started (planned)

| Feature | Status | Notes |
| --- | --- | --- |
| Repo + control plane (hooks, CI scripts, commands) | ✅ | Sprint 0 |
| Walking-skeleton API `/healthz` on Fargate (Terraform) | ✅ | Sprint 1, build-only |
| Frontend skeleton (Next.js + Tailwind, home/login/register) | ✅ | Sprint 1 design port |
| 17-table PostgreSQL schema + Alembic migrations | ✅ | Sprint 2 |
| Multi-entry ledger schema + balance CHECKs + immutability | ✅ | Sprint 2 (writes: Sprint 4) |
| Auth: Cognito JWT validation + local-dev shortcut + `/v1/me` | ✅ | Sprint 2 |
| Frontend login/registration wired to the API | ✅ | Sprint 2 (local dev-auth) |
| RDS + ElastiCache + Cognito (Terraform) | ✅ | Sprint 2, build-only |
| Cloud deploy (`terraform apply` to AWS) | ⬜ | Author-built; not yet applied |
| Real Cognito hosted-UI + PKCE browser flow | ⬜ | Sprint 5/8 |
| Publication / plan CRUD | ⬜ | Sprint 3 |
| Idempotent subscribe / tier-change / cancel / gift + outbox | ⬜ | Sprint 3 |
| Worker, EventBridge→SQS→handlers, ledger writes, S3 receipts, DLQ | ⬜ | Sprint 4 |
| Post CRUD + `publish()` + newsletter + Redis pub/sub + SSE | ⬜ | Sprint 5 |
| Admin operability (retry / amend / discard + reconciliation) | ⬜ | Sprint 6 |
| CloudWatch alarms, k6 load test, failure-mode evidence | ⬜ | Sprint 6/7 |

## 5. Sprints

8 sprints, Phase 1. See `docs/sprint-plan.md` for canonical tasks/traces; `tasks/sprint-review.md`
for evidence.

| Sprint | Goal | Status |
| --- | --- | --- |
| 0 — Guardrails | Spec pack + CLAUDE.md + hooks + CI verification scripts | ✅ Complete |
| 1 — Foundation + walking skeleton | Monorepo, `/healthz` API, Terraform foundation, CI | ✅ Complete (build-only) |
| 2 — Schema + auth | 17-table schema, Cognito + local auth + `/me`, RDS/Redis/Cognito Terraform, local stack + functional test | 🟡 In progress |
| 3 — Commerce API + outbox | Publication/plan CRUD, subscribe/gift, idempotency, transactional outbox | ⬜ Planned |
| 4 — Worker + ledger | Outbox poller, SQS handlers, three-row ledger, S3 receipts, DLQ | ⬜ Planned |
| 5 — Publishing + newsletter + SSE | Post CRUD, `publish()`, fanout, Redis, SSE dashboard | ⬜ Planned |
| 6 — Operability | CloudWatch alarms, admin runbook, reconciliation, chaos | ⬜ Planned |
| 7 — Hardening + load | k6 load tests, p95, failure-mode evidence, scale-to-zero | ⬜ Planned |
| 8 — Polish + portfolio | README, diagrams, demo, fresh-clone test, fill ADRs | ⬜ Planned |

---

## Architecture & docs

```
apps/api      FastAPI service (auth, /healthz, /v1/me; commerce + publishing later)
apps/worker   Python worker (outbox poller + event handlers; Sprint 4)
apps/web      Next.js + TypeScript + Tailwind frontend
infra/terraform  network · ecr · alb · ecs · rds · elasticache · cognito (build-only)
docs/         SPEC.md · architecture.md · openapi.yaml · event-catalog.md · sprint-plan.md ·
              test-plan.md · adr/ · design-md/ · design/
tasks/        todo.md · lessons.md · sprint-review.md
```

Canonical sources of truth: `docs/openapi.yaml` (HTTP contract), `docs/event-catalog.md` (events),
`docs/architecture.md` (data model / backbone / operability), `docs/SPEC.md` (product scope),
`CLAUDE.md` (agent operating manual).
