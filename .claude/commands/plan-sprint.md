---
description: Plan the next/active sprint by tracing tasks to canonical artifacts
argument-hint: "[sprint id, e.g. S1]"
---

You are planning sprint **$ARGUMENTS** (or the active sprint in `tasks/todo.md` if blank).

Read, in order: `CLAUDE.md` §2 read-order, then `tasks/todo.md`, then the matching
section of `docs/sprint-plan.md`, then the relevant parts of `docs/SPEC.md` and
`docs/architecture.md`. Only consult `docs/openapi.yaml` / `docs/event-catalog.md`
if the sprint touches API or events.

Then, **without writing application code**:

1. List every task the sprint plan defines for this sprint.
2. For each task, draft a `tasks/todo.md` entry using the CLAUDE.md §16 task template
   (Trace / Assumptions / Expected behavior / Implementation notes / Tests /
   Verification commands / Result).
3. Every task MUST trace to an OpenAPI operationId, a catalog event, an ER table,
   a state transition, a sequence step, or an ADR. If a task cannot be traced, flag
   it and stop — do not invent scope.
4. Confirm the prior sprint's done-criteria and `tasks/sprint-review.md` are complete
   before proposing work on a later sprint.

Output the proposed `tasks/todo.md` additions for review. Do not begin implementation.
