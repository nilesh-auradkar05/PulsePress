#!/usr/bin/env python3
"""PulsePress Stop hook: task-board reminder.

Runs when the agent finishes responding. NON-BLOCKING: it always exits 0 and
never prevents the agent from stopping. Its only job is to nudge the operator
when the working tree has code/doc changes but `tasks/todo.md` was not touched,
per the CLAUDE.md workflow (record evidence in tasks/todo.md before claiming a
task done).

Trace: CLAUDE.md §11/§16/§18, docs/sprint-plan.md S0-T02.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def _repo_root(cwd: str) -> str | None:
    for base in (os.environ.get("CLAUDE_PROJECT_DIR"), cwd, os.getcwd()):
        if not base:
            continue
        try:
            out = subprocess.run(
                ["git", "-C", base, "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            continue
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    return None


def _changed_paths(root: str) -> list[str]:
    try:
        # --untracked-files=all so a fully-untracked dir lists its files
        # individually (e.g. `?? tasks/todo.md`) instead of collapsing to `tasks/`.
        out = subprocess.run(
            ["git", "-C", root, "status", "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []
    return [line[3:].strip() for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    cwd = payload.get("cwd", "") or ""

    root = _repo_root(cwd)
    if not root:
        return 0

    changed = _changed_paths(root)
    if not changed:
        return 0

    todo_touched = any(p.endswith("tasks/todo.md") or p == "tasks/todo.md" for p in changed)
    if todo_touched:
        return 0

    print(
        "[pulsepress] Reminder: the working tree has changes but tasks/todo.md was "
        "not updated. Per CLAUDE.md §16, record task progress and verification "
        "evidence in tasks/todo.md before treating a task as done.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
