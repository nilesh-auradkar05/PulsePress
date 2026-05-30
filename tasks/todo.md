# PulsePress Task Board

Active sprint: **Sprint 0 — Guardrails**

## Current tasks

- [x] S0-T01 — Normalize repository docs
- [x] S0-T02 — Add safety hooks and commands

---

## S0-T01 — Normalize repository docs

Trace:
- SPEC: §15 (repo layout), §16 (enforcement surface)
- Sprint plan: docs/sprint-plan.md S0-T01
- Architecture/Data model: n/a (docs only)

Assumptions:
- The canonical design pack already exists; this task verifies/normalizes it rather than
  re-authoring it. Per CLAUDE.md §3, `docs/openapi.yaml` and `docs/event-catalog.md` are the
  contract docs — no duplicate `api-contract.md`/`event-model.md` (confirmed with user).
- Ops docs `local-dev.md` / `deployment.md` / `observability.md` are added as short stubs now
  and filled in their own sprints (confirmed with user).

Expected behavior:
- All local markdown links resolve; OpenAPI parses; no internally contradictory rules.

Implementation notes:
- Fixed CLAUDE.md self-referential clause ("Do not rely on `CLAUDE.md`; reserved for Codex")
  → now points the Codex-reserved note at a future `AGENTS.md`.
- Added `docs/local-dev.md`, `docs/deployment.md`, `docs/observability.md` stubs.
- Extended `.gitignore` so agent-runtime (`node_modules/`, `/package.json`, `/package-lock.json`,
  `/data/`) and import scratch (`old_files/`, `original_design_html/`, spec pack, `MANIFEST.txt`)
  are never committed; `.claude/settings.local.json` ignored, `.claude/settings.json` kept.

Tests:
- Markdown links resolve for all local docs.
- OpenAPI parses.

Verification commands:
- `python3 scripts/ci/validate_openapi.py docs/openapi.yaml`
- `python3 scripts/ci/check_docs_links.py docs CLAUDE.md README.md`
- `git check-ignore node_modules data package.json old_files`

Result: **passed** (see Evidence log).

---

## S0-T02 — Add safety hooks and commands

Trace:
- CLAUDE.md: §12 (terraform/AWS safety), §15 (security), §16 (workflow), §20 (hard stops)
- SPEC: §16 (enforcement surface)
- Sprint plan: docs/sprint-plan.md S0-T02

Assumptions:
- Hooks/CI are Python 3, stdlib-only (PyYAML used opportunistically with a structural fallback),
  runnable before any app venv exists.
- Claude Code `PreToolUse` (exit 2 = block) / `Stop` hook schema; commands invoked via
  `$CLAUDE_PROJECT_DIR`.

Expected behavior:
- `.env` reads, secret dumps, `terraform apply|destroy`, and broad-destructive shell are blocked.
- `terraform validate|fmt|plan` and benign commands are allowed.
- A Stop reminder fires when the tree changed but `tasks/todo.md` did not (non-blocking).
- Slash commands enforce the CLAUDE.md read-order / done-criteria workflow.

Implementation notes:
- `scripts/hooks/pretool_guard.py` (pure `evaluate()` + stdin/exit plumbing; fails open).
- `scripts/hooks/stop_verify.py` (non-blocking todo.md reminder).
- `.claude/settings.json` wires PreToolUse(Bash + Read|Edit|Write|NotebookEdit) and Stop, plus
  a defensive `permissions.deny` list (`.env` reads, `terraform apply|destroy`).
- `.claude/commands/`: plan-sprint, implement-task, verify-task, review-diff, write-adr, prep-portfolio.
- `.claude/agents/.gitkeep` (no custom subagents in Sprint 0 — out of scope).
- `scripts/ci/`: validate_openapi.py, check_docs_links.py, test_agent_hooks.py.

Tests:
- `.env` read blocked; `terraform apply` blocked; `terraform validate` allowed; `rm -rf /` blocked.

Verification commands:
- `python3 scripts/ci/test_agent_hooks.py`

Result: **passed** — 18/18 guard cases (see Evidence log).

---

## Evidence log

`python3 scripts/ci/test_agent_hooks.py` → exit 0:
```
[PASS] read .env / read nested .env.prod / read secrets file        -> block
[PASS] read normal source                                           -> allow
[PASS] terraform apply / terraform destroy                          -> block
[PASS] terraform validate / fmt / plan                              -> allow
[PASS] cat .env / source .env / printenv dump                       -> block
[PASS] rm -rf / / rm -rf ~ / force push main                        -> block
[PASS] benign ls / rm -f build/tmp.log / uv run pytest              -> allow
OK: all 18 guard cases passed.
```

`python3 scripts/ci/validate_openapi.py docs/openapi.yaml` → exit 0:
```
OK: OpenAPI 3.1.0 parsed; 21 paths, all with >=1 operation.
```

`python3 scripts/ci/check_docs_links.py docs CLAUDE.md README.md` → exit 0:
```
OK: all local markdown links resolve across 39 file(s).
```

Repo hygiene — `git check-ignore` confirms ignored: `node_modules`, `data`, `package.json`,
`package-lock.json`, `old_files`, `original_design_html`, `pulsepress_revised_spec_pack_v1_3`,
`MANIFEST.txt`. `git status --porcelain` would stage only: `.gitignore`, `README.md` (pre-existing),
`.claude/`, `CLAUDE.md`, `docs/`, `scripts/`, `tasks/`.
