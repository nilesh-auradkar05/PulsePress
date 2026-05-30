# Sprint Reviews

## Sprint 0 — Guardrails

Status: **Complete.**

### Review

Stood up the Claude Code control plane on top of the already-complete design pack. No
application code was written. Delivered the two canonical tasks:

- **S0-T01 Normalize repository docs** — verified the existing design pack (OpenAPI parses,
  all local markdown links resolve), fixed a self-contradictory clause in `CLAUDE.md`, added
  `local-dev.md` / `deployment.md` / `observability.md` stubs, and made `.gitignore` cover
  agent-runtime and import-scratch artifacts so they can never be committed.
- **S0-T02 Add safety hooks and commands** — added a PreToolUse safety guard
  (`scripts/hooks/pretool_guard.py`) + a non-blocking Stop reminder
  (`scripts/hooks/stop_verify.py`), wired them in `.claude/settings.json` with a defensive
  `permissions.deny` layer, authored six slash commands, and added three CI verification scripts.

### Evidence

- `python3 scripts/ci/test_agent_hooks.py` → **18/18 guard cases pass** (`.env`/secret reads,
  `terraform apply|destroy`, `cat/source .env`, `printenv`, `rm -rf /`, force-push to main all
  blocked; `terraform validate|fmt|plan` and benign commands allowed).
- `python3 scripts/ci/validate_openapi.py docs/openapi.yaml` → OpenAPI 3.1.0, 21 paths, all with ≥1 operation.
- `python3 scripts/ci/check_docs_links.py docs CLAUDE.md README.md` → all local links resolve across 39 files.
- `git check-ignore` confirms `node_modules`, `data`, `package.json`, `package-lock.json`,
  `old_files`, `original_design_html`, `pulsepress_revised_spec_pack_v1_3`, `MANIFEST.txt` are ignored.
- Full command outputs recorded in `tasks/todo.md` Evidence log.

### Known issues

- `validate_openapi.py` does full validation only when PyYAML is importable (present here); it
  degrades to a structural line-scan otherwise. Acceptable for Sprint 0 — revisit in CI (Sprint 1+).
- The guard is advisory/heuristic (fails open on malformed input); `permissions.deny` is the
  hard backstop for `.env` reads and `terraform apply|destroy`.
- Root `README.md` still carries spec-pack placeholder text (full rewrite is Sprint 8 scope).

### Next sprint gate

Sprint 1 — Foundation + walking-skeleton deploy (S1-T01 monorepo skeleton: `apps/api`,
`apps/worker`, `apps/web`, `infra/terraform`; then FastAPI `/healthz` deployed to ECS Fargate).
Gate satisfied: Sprint 0 tasks checked, evidence recorded, lessons captured.

### Portfolio artifact

The committable control plane itself: hooks + guard + slash commands + CI verification scripts
demonstrating disciplined, spec-driven agent operation before any feature code.
