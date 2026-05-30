# PulsePress Local Development

> **Status: stub.** Filled in during **Sprint 1** (foundation + local stack).
> Canonical execution detail lives in `docs/sprint-plan.md` (Sprint 1) and the
> repository layout in `docs/SPEC.md` §15.

This document will describe how to run PulsePress locally:

- `docker-compose.yml` services (PostgreSQL, Redis, LocalStack/SQS, MinIO/S3 as applicable).
- `scripts/dev/up.sh` / `scripts/dev/down.sh` one-command start/stop.
- Local auth shortcut router gated by `ENVIRONMENT=local` (never present in production — CLAUDE.md §15).
- Running the API (`apps/api`), worker (`apps/worker`), and web (`apps/web`) against the local stack.
- The verification families in `CLAUDE.md` §11.

Until Sprint 1, the only runnable tooling is the Sprint 0 control plane under `scripts/ci/`.
