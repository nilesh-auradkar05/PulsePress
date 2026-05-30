---
description: Run a task's verification family and record evidence
argument-hint: "<task id, e.g. S3-T04>"
---

Verify task **$ARGUMENTS**.

1. Find the task's `Verification commands` in `tasks/todo.md` / `docs/sprint-plan.md`.
2. Run the relevant subset of the CLAUDE.md §11 verification families for the surfaces
   the task touched:
   - Backend: `cd apps/api && uv run ruff check && uv run pyright && uv run pytest`
   - Worker:  `cd apps/worker && uv run ruff check && uv run pyright && uv run pytest`
   - Frontend: `cd apps/web && pnpm lint && pnpm typecheck && pnpm test && pnpm build`
   - Infra:   `cd infra/terraform/environments/dev && terraform fmt -check && terraform validate`
   - Control plane: `python3 scripts/ci/validate_openapi.py docs/openapi.yaml`,
     `python3 scripts/ci/check_docs_links.py docs CLAUDE.md`,
     `python3 scripts/ci/test_agent_hooks.py`
3. Tests must verify behavior, not internals (CLAUDE.md §11 forbidden list).
4. Paste the actual command outputs (or failure summaries) into the task's `tasks/todo.md`
   `Result` block. Never report a task as passed without recorded evidence.

If anything fails, summarize the failure and stop; do not mark the task done.
