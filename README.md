# PulsePress Revised Spec Pack v1.1

This pack separates:

- Architecture: `docs/architecture.md`
- Execution: `docs/sprint-plan.md`, `docs/test-plan.md`, `tasks/*`
- Agent enforcement: `AGENTS.md`, `CLAUDE.md`
- Contracts: `docs/openapi.yaml`, `docs/event-catalog.md`
- Product scope: `docs/SPEC.md`

Major fixes applied:

1. Replaced impossible ledger cross-row CHECK on `ledger_entries` with `ledger_transactions`.
2. Required idempotency for all commerce mutations, including free subscription, tier change, cancel, gift, and admin recovery verbs.
3. Unified canonical paths around `docs/openapi.yaml` and `docs/event-catalog.md`.
4. Added `user_feed_events` and reader feed endpoints to match per-subscriber fanout scope.
5. Renamed `ledger.entry.created` to `ledger.transaction.recorded`.
6. Clarified tier-change behavior for Phase 1.
7. Clarified newsletter recipient rules.
8. Replaced fake HMAC admin signature requirement with typed operator confirmation.
9. Added detailed sprint task plan and concrete test matrix.
10. Added shared `AGENTS.md` so Claude and Codex follow one rule source.
