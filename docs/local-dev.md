# PulsePress Local Development

How to run and test PulsePress on your machine. Canonical execution detail lives in
`docs/sprint-plan.md`; repository layout in `docs/SPEC.md` §15.

## Prerequisites

- **Docker** + Docker Compose (the local stack).
- **Python 3.12** + **uv** (backend dev/tests).
- **Node 20+** + **pnpm 9** (frontend; `corepack enable` then `corepack prepare pnpm@9.15.9 --activate`).
- **Terraform 1.6+** (infra `fmt`/`validate` only — never `apply` locally).

## One-command stack

```bash
scripts/dev/up.sh      # build + start: Postgres, Redis, run migrations, API, web
scripts/dev/down.sh    # stop everything (add -v to drop the database volume)
```

Services and ports:

| Service | URL / port | Notes |
| --- | --- | --- |
| API | http://localhost:8000 | FastAPI; `/healthz`, `/v1/me`, and (local only) `/local/auth/*` |
| web | http://localhost:3000 | Next.js. If 3000 is taken, edit the `web` port mapping in `docker-compose.yml` |
| Postgres | localhost:5432 | db/user/pass all `pulsepress` (dev-only) |
| Redis | localhost:6379 | present for parity; wired in a later sprint |

The `migrate` service runs `alembic upgrade head` before the API starts, so the schema is always current.

## Database schema (Alembic)

```bash
# Apply all migrations to the running stack's Postgres:
scripts/dev/migrate.sh                       # = docker compose run --rm migrate

# Work against the schema directly (from apps/api, with PULSEPRESS_DATABASE_URL set):
cd apps/api
uv run alembic upgrade head                  # apply
uv run alembic downgrade -1                   # roll back one revision
uv run alembic revision --autogenerate -m "describe change"   # create a new migration
```

The 17 Phase-1 tables, their constraints (partial-unique active subscription, ledger balance CHECKs,
unique keys), and append-only immutability are defined in `apps/api/app/models/` and materialized by
`apps/api/alembic/versions/`.

## Auth in local dev

Production auth is Cognito (ADR-0002). Locally, a **dev-auth shortcut** is mounted only when
`ENVIRONMENT=local` (never in production — CLAUDE.md §15):

- `POST /local/auth/register {email, display_name}` → creates a user, returns a dev JWT + the user.
- `POST /local/auth/login {email}` → returns a dev JWT for an existing user.
- The token is sent as `Authorization: Bearer <token>`; `GET /v1/me` returns the current user.

## Verify it works (functional test)

With the stack up:

```bash
curl -fsS localhost:8000/healthz

# register -> capture the token
TOKEN=$(curl -fsS -X POST localhost:8000/local/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com","display_name":"Ada Lovelace"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -fsS localhost:8000/v1/me -H "Authorization: Bearer $TOKEN"   # -> the user JSON
curl -fsS -X POST localhost:8000/local/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"ada@example.com"}'   # -> token
```

In the browser, open http://localhost:3000 → **Get Started / Sign in**, register or log in, and the
header shows "Hi, <name>". The same `/local/auth/*` + `/v1/me` calls power that flow.

## Test suites

```bash
# Backend (needs Postgres; point TEST_DATABASE_URL at a disposable DB)
cd apps/api
export TEST_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress_test
uv run ruff check && uv run pyright && uv run pytest

# Frontend
pnpm --dir apps/web lint && pnpm --dir apps/web typecheck && pnpm --dir apps/web build

# Infra (build-only)
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform/environments/dev init -backend=false
terraform -chdir=infra/terraform/environments/dev validate
```

CI (`.github/workflows/ci.yml`) runs all of these on every push/PR, with a Postgres service for the
backend job.
