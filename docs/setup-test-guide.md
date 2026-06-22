# PulsePress Setup & Test Guide

This is the **cumulative** local setup-and-test walkthrough for PulsePress. It is
updated **after each sprint completes**: every sprint adds a section with the
sprint name, the sprint goal, and step-by-step **setup + testing** instructions
that state the expected behavior of each functionality delivered in that sprint.

- Run sprints in order; each builds on the previous one's stack.
- Production / AWS setup lives in
  [`aws-production-setup-guide.md`](aws-production-setup-guide.md), not here.
- Local auth is a **development shortcut** (passwordless, `PULSEPRESS_ENVIRONMENT=local`
  only) — never production Cognito PKCE.
- Do not copy third-party (e.g. Medium) article bodies into seed data; demo
  content is original and first-party.

---

## Prerequisites (shared)

Required local tools:

```bash
docker compose version
python3 --version
uv --version
node --version
pnpm --version
terraform version
jq --version
```

Recommended Node setup:

```bash
corepack enable
corepack prepare pnpm@9.15.9 --activate
```

### One-command stack

```bash
scripts/dev/up.sh      # build + start: Postgres, Redis, run migrations, API, web
scripts/dev/down.sh    # stop everything (add -v to also drop the database volume)
```

| Service  | URL / port              | Notes                                   |
| -------- | ----------------------- | --------------------------------------- |
| API      | http://localhost:8000   | FastAPI; `/healthz`, `/v1/*`, local auth |
| web      | http://localhost:3000   | Next.js                                 |
| Postgres | localhost:5432          | db/user/pass all `pulsepress` (dev only) |
| Redis    | localhost:6379          | present for parity; wired in Sprint 5   |

### Shell conventions used below

```bash
# Most authenticated calls reuse $TOKEN. After registering/logging in (Sprint 2),
# capture it once:
TOKEN=$(curl -fsS -X POST http://localhost:8000/local/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"demo@example.com"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# A fresh idempotency key (≥16 chars) for money-shaped writes (Sprint 3):
newkey() { python3 -c "import uuid;print(uuid.uuid4().hex)"; }
```

### CI-parity verification (any sprint)

```bash
# Backend
cd apps/api
uv run ruff check && uv run pyright
TEST_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress_test uv run pytest
cd ../..

# Frontend
pnpm --dir apps/web lint && pnpm --dir apps/web typecheck && pnpm --dir apps/web build

# Docs + guardrails
python3 scripts/ci/validate_openapi.py docs/openapi.yaml
python3 scripts/ci/check_docs_links.py docs CLAUDE.md README.md
python3 scripts/ci/test_agent_hooks.py

# Infra (build-only)
terraform -chdir=infra/terraform/environments/dev fmt -check
terraform -chdir=infra/terraform/environments/dev validate
```

---

## Sprint 1 — Foundation + walking-skeleton deploy

### Goal

A runnable monorepo and a deployable walking skeleton: the local Docker stack
plus a FastAPI `/healthz` probe (no auth). De-risk the cloud by shipping a tiny
slice first.

### Setup

```bash
scripts/dev/up.sh
```

### Testing

**Health probe** — the API is up and self-describing, no auth required:

```bash
curl -fsS http://localhost:8000/healthz | jq .
```

Expected: HTTP 200 and a body like
`{"service":"pulsepress-api","version":"0.1.0","status":"ok"}`. The same probe
backs the container healthcheck (`docker compose ps` shows the API `healthy`).

---

## Sprint 2 — Schema + Auth

### Goal

The data + identity foundation: the 17-table PostgreSQL schema (Alembic), Cognito
JWT validation, a local-dev auth shortcut, and `GET /v1/me`. The Sprint-1
**content-MVP acceleration** (publication/post CRUD, the demo seed, and the
API-backed web app) landed alongside this sprint and is exercised here too.

### Setup

Migrations run automatically via the `migrate` compose service on `up.sh`. To run
them by hand, or to create the disposable test database:

```bash
scripts/dev/migrate.sh                      # alembic upgrade head against the stack DB

docker compose exec -T db psql -U pulsepress -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname='pulsepress_test'"
docker compose exec -T db createdb -U pulsepress pulsepress_test   # if missing
```

The web app must run in local mode (compose sets these automatically):

```bash
NEXT_PUBLIC_AUTH_MODE=local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Testing

**1. Schema & migrations** — the full schema applies and reverses cleanly:

```bash
cd apps/api
uv run alembic upgrade head     # -> 17 tables + alembic_version
uv run alembic downgrade base   # -> reverses cleanly
uv run alembic upgrade head
cd ../..
```

Expected: `upgrade head` creates the 17 Phase-1 tables, the partial-unique active
subscription index, both `ledger_transactions` balance CHECKs, and the unique
keys; `downgrade base` drops them without error.

**2. Local auth + `/v1/me`** — register/login issue a bearer token; `/v1/me`
gates on it:

```bash
# Register (409 if the user already exists -> use login instead)
TOKEN=$(curl -fsS -X POST http://localhost:8000/local/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","display_name":"Demo Writer"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -fsS http://localhost:8000/v1/me -H "Authorization: Bearer $TOKEN" | jq .
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8000/v1/me   # no token
```

Expected: `/v1/me` with a valid token → 200 and the `demo@example.com` user;
without a token → **401** (RFC 7807 problem body with a `correlation_id`).

**3. Immutability** — append-only tables reject mutation at the database level:

```bash
docker compose exec -T db psql -U pulsepress -d pulsepress -c \
  "UPDATE ledger_transactions SET currency='EUR';"
```

Expected: the statement is rejected by the `pulsepress_block_immutable_mutation`
trigger (error: `... is immutable and cannot be updated or deleted`). (No rows
exist yet, but the trigger fires before row evaluation.)

**4. Content MVP — API** — authenticated publication/post CRUD and the publish
event-door:

```bash
PUB_ID=$(curl -fsS -X POST http://localhost:8000/v1/publications \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"handle":"demo-notes","name":"Demo Notes","description":"Smoke pub"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

POST_ID=$(curl -fsS -X POST "http://localhost:8000/v1/publications/${PUB_ID}/posts" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Local smoke post","body":"Proves local CRUD works.","visibility":"free"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -fsS -X POST "http://localhost:8000/v1/posts/${POST_ID}/publish" \
  -H "Authorization: Bearer $TOKEN" | jq .
curl -fsS -X POST "http://localhost:8000/v1/posts/${POST_ID}/publish" \
  -H "Authorization: Bearer $TOKEN" | jq .
curl -fsS -X DELETE "http://localhost:8000/v1/posts/${POST_ID}" \
  -H "Authorization: Bearer $TOKEN" | jq .status
```

Expected: create → 201; first publish → `newsletter_status:"queued"` and exactly
one immutable `post_versions` snapshot + one `post.published` outbox row; second
publish → `already_processed`, **no** duplicate snapshot/outbox; archive → status
`archived`.

**5. Demo seed (idempotent)**:

```bash
cd apps/api
PULSEPRESS_ENVIRONMENT=local \
PULSEPRESS_LOCAL_JWT_SECRET=local-dev-only-secret-change-me-in-real-environments \
PULSEPRESS_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress \
uv run python -m app.scripts.seed_demo_content \
  --owner-sub local:demo@example.com --owner-email demo@example.com --owner-name "Demo Writer"
cd ../..
```

Expected: first run reports created users/publications/posts/versions; a second
run reports **reused** records and creates no duplicates.

**6. Content MVP — browser** — open `http://localhost:3000`:

1. Register or sign in as `demo@example.com`.
2. `/home` shows only that user's owned publications/posts.
3. Create a draft → edit it → publish it → it appears on `/explore`.
4. "Read more" opens the post; archive it → it disappears from reader views.
5. Search from the header/Explore → deterministic results.
6. Register a second user → their `/home` does **not** show the first user's
   publications.
7. Sign out, press **Back/Forward** → protected content is **not** restored
   (redirected to login).

---

## Sprint 3 — Commerce API + Outbox

### Goal

The money-shaped write boundary: author-configured subscription **plans**, **free
and paid subscriptions**, **tier change**, **cancel**, and one-time **gifts**.
Every commerce mutation requires an `Idempotency-Key` and atomically writes the
business row + an idempotency record + a transactional **outbox** event, returning
a transparent three-way **bill** (author / platform / tax). Events accumulate
**unprocessed** — the poller, worker, and ledger are Sprint 4, so **no ledger rows
are written by the API**.

### Setup

Bring the stack up and prepare an **owner** (with a publication + plans) and a
separate **subscriber**:

```bash
scripts/dev/up.sh

# Owner token (register, or login if the user exists)
OWNER=$(curl -fsS -X POST http://localhost:8000/local/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@example.com","display_name":"Owner"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# A publication owned by Owner
PUB_ID=$(curl -fsS -X POST http://localhost:8000/v1/publications \
  -H "Authorization: Bearer $OWNER" -H 'Content-Type: application/json' \
  -d '{"handle":"owner-zine","name":"Owner Zine"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# A subscriber (different user — self-subscribe is forbidden)
READER=$(curl -fsS -X POST http://localhost:8000/local/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"reader@example.com","display_name":"Reader"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

newkey() { python3 -c "import uuid;print(uuid.uuid4().hex)"; }
```

### Testing

**1. Create plans (owner-only)** — free and paid tiers:

```bash
PAID_PLAN=$(curl -fsS -X POST "http://localhost:8000/v1/publications/${PUB_ID}/plans" \
  -H "Authorization: Bearer $OWNER" -H 'Content-Type: application/json' \
  -d '{"name":"Supporter","monthly_price_cents":500,"allow_open_amount":true}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

FREE_PLAN=$(curl -fsS -X POST "http://localhost:8000/v1/publications/${PUB_ID}/plans" \
  -H "Authorization: Bearer $OWNER" -H 'Content-Type: application/json' \
  -d '{"name":"Free","monthly_price_cents":0}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -fsS "http://localhost:8000/v1/publications/${PUB_ID}/plans" \
  -H "Authorization: Bearer $READER" | jq '.[].name'

curl -fsS "http://localhost:8000/v1/publications/${PUB_ID}" \
  -H "Authorization: Bearer $READER" | jq '.active_plans[].name'
```

Expected: both create → 201; list/detail → `["Free","Supporter"]` (any auth'd
user can read). A non-owner POST → **403**; negative price or `currency != "USD"`
→ **422**.

**2. Paid subscribe returns the bill** — `amount_cents:500` → author 450 / platform
50 / tax 40 / total 540:

```bash
KEY=$(newkey)
curl -fsS -X POST http://localhost:8000/v1/subscriptions \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d "{\"publication_id\":\"$PUB_ID\",\"plan_id\":\"$PAID_PLAN\",\"amount_cents\":500}" | jq .
```

Expected: HTTP 201, `tier:"paid"`, `status:"active"`, and
`bill = {amount_cents:500, author_net_cents:450, platform_fee_cents:50, tax_cents:40, total_charged_cents:540}`.

**2a. Publication summary and paid-post entitlement** — the summary is DB-backed
until Redis caching lands later; the paid post body is visible to the paid
subscriber:

```bash
PAID_POST=$(curl -fsS -X POST "http://localhost:8000/v1/publications/${PUB_ID}/posts" \
  -H "Authorization: Bearer $OWNER" -H 'Content-Type: application/json' \
  -d '{"title":"Paid reader smoke","body":"Subscriber-only body.","visibility":"paid"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -fsS -X POST "http://localhost:8000/v1/posts/${PAID_POST}/publish" \
  -H "Authorization: Bearer $OWNER" | jq .

curl -fsS "http://localhost:8000/v1/posts/${PAID_POST}" \
  -H "Authorization: Bearer $READER" | jq '{entitled, body}'

curl -fsS "http://localhost:8000/v1/publications/${PUB_ID}/summary" \
  -H "Authorization: Bearer $READER" \
  | jq '{subscriber_count, post_count, recent_revenue_cents}'
```

Expected: post read returns `entitled:true` and the body for the paid subscriber;
summary returns `subscriber_count >= 1`, `post_count >= 1`, and
`recent_revenue_cents >= 500`.

**3. Idempotent replay** — re-POST with the **same key + same body**:

```bash
curl -fsS -D - -o /dev/null -X POST http://localhost:8000/v1/subscriptions \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d "{\"publication_id\":\"$PUB_ID\",\"plan_id\":\"$PAID_PLAN\",\"amount_cents\":500}" \
  | grep -i 'HTTP/\|idempotency-replayed'
```

Expected: HTTP 201 with header `idempotency-replayed: true`, the **same** response
body, and **no** second subscription/outbox row. Concurrent same-key writes are
covered by the API test suite and must also produce one business row plus one
replay.

**4. Idempotency conflict** — same key, **different** body → 422:

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/v1/subscriptions \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d "{\"publication_id\":\"$PUB_ID\",\"plan_id\":\"$FREE_PLAN\",\"amount_cents\":0}"
```

Expected: **422** (idempotency-conflict).

**5. Guard rails**:

```bash
# Self-subscribe (owner subscribes to own publication) -> 403
curl -fsS -o /dev/null -w 'self_subscribe=%{http_code}\n' -X POST http://localhost:8000/v1/subscriptions \
  -H "Authorization: Bearer $OWNER" -H "Idempotency-Key: $(newkey)" \
  -H 'Content-Type: application/json' \
  -d "{\"publication_id\":\"$PUB_ID\",\"plan_id\":\"$PAID_PLAN\",\"amount_cents\":500}"

# Duplicate active subscription (new key) -> 409
curl -fsS -o /dev/null -w 'duplicate=%{http_code}\n' -X POST http://localhost:8000/v1/subscriptions \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $(newkey)" \
  -H 'Content-Type: application/json' \
  -d "{\"publication_id\":\"$PUB_ID\",\"plan_id\":\"$PAID_PLAN\",\"amount_cents\":500}"

# Missing Idempotency-Key -> 422
curl -fsS -o /dev/null -w 'missing_key=%{http_code}\n' -X POST http://localhost:8000/v1/subscriptions \
  -H "Authorization: Bearer $READER" -H 'Content-Type: application/json' \
  -d "{\"publication_id\":\"$PUB_ID\",\"plan_id\":\"$PAID_PLAN\",\"amount_cents\":500}"

# Amount below the plan floor -> 422
curl -fsS -o /dev/null -w 'below_min=%{http_code}\n' -X POST http://localhost:8000/v1/subscriptions \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $(newkey)" \
  -H 'Content-Type: application/json' \
  -d "{\"publication_id\":\"$PUB_ID\",\"plan_id\":\"$PAID_PLAN\",\"amount_cents\":300}"
```

Expected: `self_subscribe=403`, `duplicate=409`, `missing_key=422`, `below_min=422`.

**6. Tier change & cancel** — capture the subscription id, then PATCH and DELETE:

```bash
SUB_ID=$(curl -fsS http://localhost:8000/v1/publications/${PUB_ID}/plans -H "Authorization: Bearer $READER" >/dev/null; \
  docker compose exec -T db psql -U pulsepress -d pulsepress -tAc \
  "SELECT id FROM subscriptions WHERE status='active' ORDER BY created_at DESC LIMIT 1")

# Change tier (idempotent) -> 200, bill null (no new charge this period)
curl -fsS -X PATCH "http://localhost:8000/v1/subscriptions/${SUB_ID}" \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $(newkey)" \
  -H 'Content-Type: application/json' \
  -d "{\"new_plan_id\":\"$PAID_PLAN\",\"new_amount_cents\":1500}" | jq '{status,tier,bill}'

# Cancel (idempotent) -> 200 canceled, access retained until period_end
curl -fsS -X DELETE "http://localhost:8000/v1/subscriptions/${SUB_ID}" \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $(newkey)" | jq '{status,access_until}'

# Cancel again (new key) -> 200 no-op, no duplicate event
curl -fsS -o /dev/null -w 'cancel_again=%{http_code}\n' -X DELETE \
  "http://localhost:8000/v1/subscriptions/${SUB_ID}" \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $(newkey)"
```

Expected: tier change → 200, `bill:null`, `amount_cents` updated, one
`subscription.tier_changed` outbox row; cancel → 200, `status:"canceled"`,
`access_until` set to `period_end`, one `subscription.canceled` row; second
cancel → `cancel_again=200` with **no** additional event.

**7. Gifts**:

```bash
# Happy path: 1000c -> author 900 / platform 100 / tax 80 / total 1080
curl -fsS -X POST http://localhost:8000/v1/gifts \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $(newkey)" \
  -H 'Content-Type: application/json' \
  -d '{\"publication_id\":\"$PUB_ID\",\"amount_cents\":1000,\"message\":\"Loved this!\"}' | jq .

# Self-gift -> 403 ; below 50c -> 422
curl -fsS -o /dev/null -w 'self_gift=%{http_code}\n' -X POST http://localhost:8000/v1/gifts \
  -H "Authorization: Bearer $OWNER" -H "Idempotency-Key: $(newkey)" \
  -H 'Content-Type: application/json' -d "{\"publication_id\":\"$PUB_ID\",\"amount_cents\":1000}"

curl -fsS -o /dev/null -w 'below_min=%{http_code}\n' -X POST http://localhost:8000/v1/gifts \
  -H "Authorization: Bearer $READER" -H "Idempotency-Key: $(newkey)" \
  -H 'Content-Type: application/json' -d "{\"publication_id\":\"$PUB_ID\",\"amount_cents\":49}"
```

Expected: gift → 201, `status:"pending"`, `bill.total_charged_cents:1080`;
`self_gift=403`; `below_min=422`. Concurrent same-key gifts are covered by the
API test suite and must produce one gift row plus one replay.

**8. Outbox accumulates; ledger stays empty** — confirm the async backbone is
fed but unprocessed:

```bash
docker compose exec -T db psql -U pulsepress -d pulsepress -c \
  "SELECT event_type, status, count(*) FROM outbox_events GROUP BY 1,2 ORDER BY 1;"
docker compose exec -T db psql -U pulsepress -d pulsepress -c \
  "SELECT count(*) AS ledger_transactions FROM ledger_transactions;"
```

Expected: `outbox_events` contains `subscription.created`, `subscription.tier_changed`,
`subscription.canceled`, and `gift.sent` rows, all `status='pending'`; each row's
`payload` carries the full envelope (`event_id`, `correlation_id`, nested
`payload`). `ledger_transactions` count is **0** (the worker is Sprint 4).

**9. Browser smoke for Sprint 3** — open `http://localhost:3000`:

1. Sign in locally as the owner.
2. Go to **New Post**, select/create a publication, create a free or paid plan,
   and save a draft.
3. Publish the draft, sign out, then sign in as a reader.
4. Open the post. If it is paid, use the Subscribe panel to subscribe; the body
   should unlock after the API confirms the subscription.
5. Use the Send gift panel; expected success text includes the total charged.
6. Open the profile menu: appearance and sign-out work; account-destructive
   settings are disabled until backend workflows exist.

---

## Sprint 4 — Worker + Multi-entry Ledger

### Goal

Process the Sprint-3 commerce outbox safely: publish supported commerce events,
validate their durable source rows, write one balanced three-entry ledger for
paid sources, and persist an immutable receipt. Local mode replaces AWS delivery
with an in-process queue; it is the quickest end-to-end validation path.

### Setup

Run the Sprint-3 paid subscription and gift steps above first. They leave
`subscription.created` and `gift.sent` events pending in `outbox_events`.

Run one local worker cycle from a second terminal:

```bash
cd apps/worker
PULSEPRESS_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress \
PULSEPRESS_WORKER_MODE=local \
PULSEPRESS_WORKER_RUN_ONCE=true \
PULSEPRESS_LOCAL_ARTIFACT_DIRECTORY=/tmp/pulsepress-artifacts \
uv run python3 -m pulsepress_worker.main
cd ../..
```

Expected: the worker logs a cycle with claimed/published/processed commerce
events. Re-running the command is safe: previously successful events are no
longer pending, and duplicate delivery is guarded by `event_id`.

Run the same one-cycle command a second time after paid sources are processed.
The first cycle writes `ledger.transaction.recorded` into the outbox; the second
cycle publishes that worker-originated event.

Two optional knobs govern crash recovery (defaults are correct locally):

- `PULSEPRESS_WORKER_EVENT_LOCK_SECONDS` (default 300) — how long a claimed
  event's lease is held before another cycle may reclaim it. A worker that
  crashes mid-handle releases its event when this lease expires.
- `PULSEPRESS_WORKER_MAX_RECEIVE_COUNT` (default 5) — the per-event attempt
  ceiling. Terminal failure is decided by this **claim attempt count**, never by
  the SQS receive count (which can inflate under lease contention without a
  genuine retry).

### Testing

**1. Inspect processed money events and ledger entries**:

```bash
docker compose exec -T db psql -U pulsepress -d pulsepress -c \
  "SELECT source_type, source_id, total_charged_cents, currency FROM ledger_transactions ORDER BY created_at;"
docker compose exec -T db psql -U pulsepress -d pulsepress -c \
  "SELECT account, amount_cents FROM ledger_entries ORDER BY created_at;"
```

Expected: every paid subscription/gift has one ledger transaction and exactly
three `author`, `platform`, and `tax` entries. For the walkthrough's 500-cent
subscription, entries are 450/50/40 and total charged is 540; for the 1000-cent
gift, entries are 900/100/80 and total charged is 1080.

**2. Inspect receipts and delivery states**:

```bash
find /tmp/pulsepress-artifacts/receipts -type f -name '*.json' -print
docker compose exec -T db psql -U pulsepress -d pulsepress -c \
  "SELECT event_type, status, publish_attempts, terminal_at FROM outbox_events ORDER BY created_at;"
```

Expected: a receipt JSON exists for every paid source. After the second cycle,
processed Sprint-4 commerce/kernel events are `published`. A `post.published`
row remains `pending`: Sprint 5 owns newsletter routing and handlers, so it
must not be falsely marked delivered by the Sprint-4 worker. A crash between the
receipt write and the ledger commit self-heals on a later cycle: the lease
expires, the event is reclaimed, and the idempotent receipt plus
`UNIQUE(source_type, source_id)` prevent any double ledger write.

**3. Run the worker and migration regressions**:

```bash
cd apps/api
TEST_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress_test \
uv run pytest tests/test_migrations.py -q
cd ../worker
TEST_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress_test \
uv run ruff check
TEST_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress_test \
uv run pyright
TEST_DATABASE_URL=postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress_test \
uv run pytest -q
cd ../..
```

Expected: the migration suite proves the exact three-entry ledger constraint and
creation-charge backfill; the 24 worker tests cover duplicate delivery, retry
backoff, write-once receipts, source conflicts, terminal failure signaling, SQS
redrive behavior, lease-based reclaim after a crash, attempt-count terminal
accounting (immune to SQS receive-count inflation), and same-`event_id` ledger
dedup on reclaim.

**4. Validate AWS infrastructure without applying it**:

```bash
terraform -chdir=infra/terraform/environments/dev fmt -check -recursive
terraform -chdir=infra/terraform/environments/dev validate
```

Expected: Terraform validates an EventBridge bus, SQS worker queue plus distinct
worker/EventBridge DLQs, private versioned receipt bucket, and a separate ECS
worker task role scoped to its bus, queue, and receipt prefix.

---

## Stop & reset

```bash
scripts/dev/down.sh        # stop the stack
scripts/dev/down.sh -v     # also drop the database volume (full reset)
```

## Known boundaries (current)

- Local auth is a development shortcut only; production browser auth is Cognito
  (see the AWS guide).
- Sprint-4 commerce/kernel events process when the worker runs. Publishing
  events remain pending for Sprint 5; newsletter fanout, SSE, and the audited
  admin recovery UI remain later work.
- Explore search is a simple deterministic filter, not Phase-2 discovery.
- Seed content is synthetic and first-party.
- Local web can exercise plan creation, subscribe, and gift flows; production
  browser auth still requires the Cognito PKCE adapter described in the AWS guide.
