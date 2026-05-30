# Lessons

Record user corrections here. Format: date / correction / root cause / prevention rule / applied.

---

## 2026-05-29 — Sprint 0 kickoff doc list diverged from canonical sprint plan

- **Correction:** The kickoff prompt listed Sprint 0 doc outputs (`docs/api-contract.md`,
  `docs/event-model.md`, `docs/local-dev.md`, `docs/deployment.md`, `docs/observability.md`)
  that (a) partly duplicated existing canonical artifacts under different names and (b) exceeded
  the canonical Sprint 0 scope. Resolved with the user: use canonical names
  (`docs/openapi.yaml`, `docs/event-catalog.md`) — no duplicates; add `local-dev`/`deployment`/
  `observability` as short stubs now; gitignore agent-runtime + import scratch non-destructively.
- **Root cause:** A free-form kickoff prompt was treated as a candidate task list while the
  repo already contained a complete, canonical design pack and a defined Sprint 0
  (`docs/sprint-plan.md` S0-T01/S0-T02).
- **Prevention rule:** Before creating or renaming any doc, reconcile the request against
  `docs/sprint-plan.md` and the CLAUDE.md §3 source-of-truth hierarchy. Never create a document
  that duplicates a canonical artifact under a new name; if the prompt and the sprint plan
  disagree, surface it and ask rather than silently choosing.
- **Applied:** Yes.
