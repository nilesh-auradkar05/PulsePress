---
description: Review the working diff against PulsePress hard rules
argument-hint: "[base ref, default HEAD]"
---

Review the current diff (`git diff $ARGUMENTS` if a base is given, otherwise
`git diff HEAD` plus staged/untracked changes) against the `CLAUDE.md` hard rules.

Flag any violation, citing file and line:

- **Write-shape (§5):** ledger rows or event emission inside API route handlers;
  outbox writes from publishing paths; business logic in route handlers instead of services.
- **Money (§6):** floats anywhere in money code/tests/schemas/models; missing round-half-up;
  `author_net_cents` not computed as residual; broken bill invariant.
- **Events (§7):** new event names or payload fields not in `docs/event-catalog.md`;
  inlined post bodies; missing `correlation_id`/`causation_id`; non-idempotent handlers.
- **API (§9):** endpoints not in `docs/openapi.yaml`; hand-edited generated schemas;
  errors not RFC 7807; missing `Idempotency-Key` on commerce mutations.
- **DB (§8):** schema change without Alembic; destructive migration; cross-row CHECK on
  `ledger_entries`; mutation paths on immutable tables.
- **Security (§15):** self-subscribe/self-gift allowed; missing owner/subscriber/admin checks;
  local-auth route reachable in production; secrets committed.
- **Scope (§4/§17):** out-of-Phase-1 features; speculative abstractions; unrelated refactors
  or formatting churn; changed lines that don't trace to the active task.

Output a checklist verdict (pass/flag per category). Do not modify files unless asked.
