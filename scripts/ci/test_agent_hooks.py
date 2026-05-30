#!/usr/bin/env python3
"""Behavioral tests for the PreToolUse safety guard.

Drives `scripts/hooks/pretool_guard.py` as a subprocess with synthetic Claude Code
hook payloads and asserts the exit code (0 = allow, 2 = block). This verifies the
guard the way Claude Code actually invokes it, not its internals.

Usage:
    python3 scripts/ci/test_agent_hooks.py

Exit codes: 0 = all cases pass, 1 = one or more failed.

Trace: docs/sprint-plan.md S0-T02 ("python scripts/ci/test_agent_hooks.py").
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUARD = os.path.normpath(os.path.join(_HERE, "..", "hooks", "pretool_guard.py"))

ALLOW, BLOCK = 0, 2

# (label, tool_name, tool_input, expected_exit)
CASES = [
    ("read .env",            "Read", {"file_path": ".env"},                          BLOCK),
    ("read nested .env.prod","Read", {"file_path": "infra/.env.production"},          BLOCK),
    ("read secrets file",    "Read", {"file_path": "config/credentials.json"},        BLOCK),
    ("read normal source",   "Read", {"file_path": "apps/api/app/main.py"},           ALLOW),
    ("terraform apply",      "Bash", {"command": "terraform apply -auto-approve"},    BLOCK),
    ("terraform destroy",    "Bash", {"command": "cd infra && terraform destroy"},    BLOCK),
    ("terraform validate",   "Bash", {"command": "terraform validate"},               ALLOW),
    ("terraform fmt",        "Bash", {"command": "terraform fmt -check"},             ALLOW),
    ("terraform plan",       "Bash", {"command": "terraform plan -out tf.plan"},      ALLOW),
    ("cat .env",             "Bash", {"command": "cat .env"},                         BLOCK),
    ("source .env",          "Bash", {"command": "source .env && echo hi"},           BLOCK),
    ("printenv dump",        "Bash", {"command": "printenv | grep AWS"},              BLOCK),
    ("rm -rf root",          "Bash", {"command": "rm -rf /"},                         BLOCK),
    ("rm -rf home",          "Bash", {"command": "rm -rf ~"},                         BLOCK),
    ("force push main",      "Bash", {"command": "git push --force origin main"},     BLOCK),
    ("benign ls",            "Bash", {"command": "ls -la"},                           ALLOW),
    ("benign rm file",       "Bash", {"command": "rm -f build/tmp.log"},              ALLOW),
    ("benign pytest",        "Bash", {"command": "uv run pytest"},                    ALLOW),
]


def run_case(tool_name: str, tool_input: dict) -> int:
    payload = json.dumps(
        {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}
    )
    proc = subprocess.run(
        [sys.executable, _GUARD],
        input=payload, capture_output=True, text=True, timeout=10,
        env={**os.environ, "PULSEPRESS_DISABLE_GUARD": "0"},
    )
    return proc.returncode


def main() -> int:
    if not os.path.exists(_GUARD):
        print(f"ERROR: guard not found at {_GUARD}", file=sys.stderr)
        return 1

    failures = 0
    for label, tool, tin, expected in CASES:
        got = run_case(tool, tin)
        ok = got == expected
        status = "PASS" if ok else "FAIL"
        verb = {ALLOW: "allow", BLOCK: "block"}
        print(f"[{status}] {label:22s} expected={verb.get(expected, expected)} got_exit={got}")
        if not ok:
            failures += 1

    print()
    if failures:
        print(f"FAIL: {failures}/{len(CASES)} guard cases failed.", file=sys.stderr)
        return 1
    print(f"OK: all {len(CASES)} guard cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
