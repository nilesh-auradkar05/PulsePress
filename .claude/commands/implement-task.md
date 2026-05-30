---
description: Implement a single traced task with the smallest correct change
argument-hint: "<task id, e.g. S3-T04>"
---

Implement task **$ARGUMENTS**.

Before editing, follow `CLAUDE.md` §16:

1. Read `CLAUDE.md`, `tasks/todo.md`, and the task's entry in `docs/sprint-plan.md`.
2. Confirm the trace (OpenAPI / event / ER table / state / sequence / ADR). If the task
   is not traceable, **stop and ask** — do not improvise (CLAUDE.md §20).
3. State your assumptions in the `tasks/todo.md` entry before coding.

Then implement, honoring the hard rules:

- Smallest change that satisfies the task; no unrelated refactors or speculative abstractions.
- Commerce vs publishing write-shape split (CLAUDE.md §5). Never write ledger rows or emit
  events from API route handlers. Business logic lives in services, not routes.
- Money is integer cents only — never floats (§6).
- No new event names/fields beyond `docs/event-catalog.md`; no endpoints beyond `docs/openapi.yaml`.
- Use Alembic for schema changes; no destructive migration without explicit approval.

After coding, run the relevant verification family (CLAUDE.md §11) and record the command
outputs in the task's `tasks/todo.md` entry. Do not claim done until checks pass and results
are recorded (§19).
