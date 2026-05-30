# PulsePress Task Board

Active sprint: **Sprint 1 — Foundation + walking-skeleton deploy**

> Sprint 0 (control plane + design pack) is complete and committed on branch
> `sprint-0-control-plane`. Sprint 1 runs on `sprint-1-foundation`.

## Current tasks

- [x] S1-T01 — Create monorepo skeleton (`apps/api`, `apps/worker`, `apps/web`, `infra/terraform`)
- [x] S1-T02 — FastAPI `/healthz`
- [x] S1-T03 — Terraform foundation (network, ECR, ALB, ECS, log group) — build-only
- [x] S1-CI — Minimal GitHub Actions CI (verification family + Sprint 0 guardrail scripts)

---

## S1-T01 — Create monorepo skeleton

Trace:
- SPEC: §15 (repository structure), §4 (approved stack)
- Sprint plan: docs/sprint-plan.md S1-T01
- Architecture/Data model: n/a (skeleton only)

Assumptions:
- Skeletons are minimal but real: each app passes its own lint/typecheck/build, no feature logic.
- Only the subpackages `/healthz` needs are created under `apps/api/app/`; the rest of the SPEC §15
  api tree (`db,domain,models,services,auth,integrations`) is added in the sprint that needs each.
- Python 3.12 + uv; frontend pnpm + Next.js (App Router) + TS + Tailwind.

Expected behavior:
- `apps/api`, `apps/worker`, `apps/web`, `infra/terraform`, `scripts`, `docs`, `tasks` exist.
- Python packages use uv; frontend uses pnpm; Dockerfiles build minimal services.

Tests / Verification:
- `cd apps/api && uv run ruff check && uv run pyright && uv run pytest`
- `cd apps/worker && uv run ruff check && uv run pyright && uv run pytest`
- `pnpm --dir apps/web install && pnpm --dir apps/web lint && pnpm --dir apps/web typecheck && pnpm --dir apps/web build`

Result: **passed** — api: ruff ok, pyright 0 errors, pytest 2/2; worker: ruff ok, pyright 0
errors, pytest 1/1; web: lint ok, typecheck ok, `next build` ok. (See Evidence log.)

---

## S1-T02 — FastAPI `/healthz`

Trace:
- Sprint plan: docs/sprint-plan.md S1-T02
- ADR: docs/adr/ADR-0006 (walking-skeleton deploy)
- OpenAPI: intentionally NOT in `docs/openapi.yaml` — sanctioned **internal** operational endpoint
  (ALB health target), not a product `/v1` route. Response is a handwritten internal schema.
  (See tasks/lessons.md 2026-05-30 decision note.)

Assumptions:
- Root path `/healthz`, no auth, no `/v1` prefix. Static JSON `{service, version, status:"ok"}`.

Expected behavior:
- `GET /healthz` returns 200 with service name, version, status; no auth required.

Tests / Verification:
- `apps/api/tests/test_health.py`: 200; body keys match `HealthResponse`; `status == "ok"`; no auth.
- Local smoke: run uvicorn, `curl -fsS localhost:8000/healthz`.

Result: **passed** — pytest 2/2; docker-compose container reported `healthy` and
`curl /healthz` returned `{"service":"pulsepress-api","version":"0.1.0","status":"ok"}`.

---

## S1-T03 — Terraform foundation (build-only)

Trace:
- Sprint plan: docs/sprint-plan.md S1-T03
- ADR: ADR-0001 (Terraform), ADR-0006 (walking skeleton), ADR-0007 (scale-to-zero)
- Architecture: §12 (cloud architecture), SPEC §14 (security)

Assumptions:
- **Build only — no `terraform apply`** (confirmed with user). Cost-minimal shape: API Fargate task
  in public subnets w/ public IP (no NAT); ALB HTTP:80 only (TLS/ACM deferred). Private subnets
  defined for Sprint 2 RDS/Redis. No RDS/Redis/SQS/EventBridge/S3/Cognito this sprint.
- Worker: ECR repo only; no worker ECS service yet (Sprint 4).
- Local Terraform binary is NOT installed → `fmt`/`validate` run in CI, not locally.

Expected behavior:
- network module; ECR repos; ALB → API target group (`/healthz` health check); ECS cluster + API
  Fargate service; CloudWatch log group. Every resource tagged project/environment. No secrets.

Tests / Verification:
- `terraform -chdir=infra/terraform/environments/dev fmt -check`
- `terraform -chdir=infra/terraform/environments/dev init -backend=false`
- `terraform -chdir=infra/terraform/environments/dev validate`
- `terraform plan` DEFERRED (needs AWS creds; build-only).

Result: **passed** — terraform 1.9.8 (fetched locally; not installed on PATH): `fmt -check
-recursive` clean, `init -backend=false` ok (aws ~> 5.0), `validate` → "The configuration is
valid." `plan`/`apply` deferred per build-only decision.

---

## S1-CI — Minimal GitHub Actions CI

Trace:
- SPEC: §4 (GitHub Actions in stack), §16 (enforcement surface)
- Added per user decision (not a named S1 task; no deploy stage).

Expected behavior:
- `.github/workflows/ci.yml` runs on push + PR: api/worker (ruff, pyright, pytest), web (lint,
  typecheck, build), terraform (fmt -check, init -backend=false, validate), guardrails (Sprint 0
  CI scripts). No deploy stage.

Tests / Verification:
- Workflow YAML is well-formed; jobs mirror the local verification family.

Result: **passed** — `.github/workflows/ci.yml` authored with api/worker/web/terraform/guardrails
jobs. Each job mirrors a verification command proven locally; first real CI run happens on push.

---

## Evidence log

### apps/api
```
uv run ruff check   -> All checks passed!
uv run pyright      -> 0 errors, 0 warnings, 0 informations
uv run pytest -q    -> 2 passed (StarletteDeprecationWarning re: httpx — harmless)
```

### apps/worker
```
uv run ruff check   -> All checks passed!
uv run pyright      -> 0 errors, 0 warnings, 0 informations
uv run pytest -q    -> 1 passed
```

### apps/web (pnpm 9.15.9 via `npm i -g pnpm@9`; corepack absent on this nvm node)
```
pnpm install        -> done (pnpm-lock.yaml generated)
pnpm lint           -> ✔ No ESLint warnings or errors
pnpm typecheck      -> tsc --noEmit, no errors
pnpm build          -> ✓ Compiled successfully; / and /_not-found prerendered (static)
```
Note: `next build` warns about multiple lockfiles (root agent-runtime `package-lock.json` is
gitignored, not part of the project). In a clean checkout / CI only `apps/web/pnpm-lock.yaml`
exists, so the warning does not occur there.

### Local walking skeleton (docker compose)
```
scripts/dev/up.sh           -> image built, container started
docker inspect health       -> healthy
curl -fsS :8000/healthz      -> {"service":"pulsepress-api","version":"0.1.0","status":"ok"}
scripts/dev/down.sh         -> container + network removed
```

### infra/terraform (terraform 1.9.8 fetched to /tmp; not on PATH)
```
terraform -chdir=infra/terraform fmt -check -recursive            -> clean
terraform -chdir=.../environments/dev init -backend=false          -> initialized (aws ~> 5.0)
terraform -chdir=.../environments/dev validate                     -> The configuration is valid.
```
`.terraform/` (675 MB providers) gitignored; `.terraform.lock.hcl` committed.

### Guardrails (Sprint 0 CI scripts — also run in CI now)
```
validate_openapi.py docs/openapi.yaml          -> OpenAPI 3.1.0, 21 paths
check_docs_links.py docs CLAUDE.md README.md   -> all links resolve, 39 files
test_agent_hooks.py                            -> 18/18 guard cases pass
```
