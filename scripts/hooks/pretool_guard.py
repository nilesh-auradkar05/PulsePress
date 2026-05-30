#!/usr/bin/env python3
"""PulsePress PreToolUse safety guard.

Reads a Claude Code PreToolUse hook payload from stdin and blocks dangerous or
out-of-scope operations before they run. Wired in `.claude/settings.json` for
the `Bash` and `Read` tools.

Contract (Claude Code hooks):
- stdin: JSON envelope with `tool_name` and `tool_input`.
- exit 0  -> allow the tool call.
- exit 2  -> block; the reason on stderr is fed back to the agent.

Design notes:
- `evaluate(tool_name, tool_input)` is a pure function so it can be unit-tested
  directly; `main()` only handles stdin/exit plumbing.
- The guard FAILS OPEN: malformed input or unexpected errors allow the call
  (exit 0) so a parsing bug never bricks the session. Security-critical denials
  are duplicated as `permissions.deny` rules in `.claude/settings.json`.
- Trace: CLAUDE.md §12/§15/§20, docs/sprint-plan.md S0-T02.
"""

from __future__ import annotations

import json
import os
import re
import sys

# --- Bash command patterns (case-insensitive) -------------------------------

# Terraform mutations are never allowed without an explicit human in the loop.
_TERRAFORM_MUTATION = re.compile(r"\bterraform\b.*\b(apply|destroy)\b")

# Reading or sourcing dotenv / secret files via the shell.
_ENV_READ = re.compile(
    r"\b(cat|less|more|head|tail|bat|nano|vi|vim|view|xxd|od|strings|source|\.)\b"
    r"[^\n|;&]*\.env(\.[\w.-]+)?\b"
)

# Dumping the whole environment (which may contain secrets).
_PRINTENV = re.compile(r"(^|[\s;&|])printenv(\s|$)|(^|[\s;&|])env\s*([|>]|$)")

# Broadly destructive filesystem / disk operations.
_DESTRUCTIVE = [
    re.compile(r"\brm\s+(-[a-z]*\s+)*-?[a-z]*[rf][a-z]*\s+(/|/\*|~|~/|\$HOME)(\s|$)"),
    re.compile(r"\bmkfs(\.\w+)?\b"),
    re.compile(r"\bdd\b[^\n]*\bof=/dev/"),
    re.compile(r">\s*/dev/sd[a-z]"),
    re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),  # fork bomb
    re.compile(r"\bchmod\s+-R\s+\d+\s+/(\s|$)"),
]

# Force-pushing to a protected branch.
_FORCE_PUSH_MAIN = re.compile(
    r"\bgit\s+push\b.*(--force\b|--force-with-lease\b|\s-f\b).*\b(main|master)\b"
)

# Secret-bearing file names for the Read tool.
_SECRET_FILE = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|\.envrc)$|secret|credential|\.pem$|id_rsa")


def _check_bash(command: str) -> str | None:
    """Return a block reason for a bash command, or None to allow."""
    cmd = command.strip()
    low = cmd.lower()

    if _TERRAFORM_MUTATION.search(low):
        return (
            "Blocked: `terraform apply`/`terraform destroy` require explicit human "
            "action this session (CLAUDE.md §12). `terraform validate|fmt|plan` are allowed."
        )
    if _ENV_READ.search(cmd):
        return "Blocked: reading/sourcing a .env file may expose secrets (CLAUDE.md §15)."
    if _PRINTENV.search(cmd):
        return "Blocked: dumping the full environment may expose secrets (CLAUDE.md §15)."
    if _FORCE_PUSH_MAIN.search(low):
        return "Blocked: force-pushing to main/master is destructive (CLAUDE.md §17)."
    for pat in _DESTRUCTIVE:
        if pat.search(cmd):
            return f"Blocked: destructive shell command matched guard pattern: {pat.pattern!r}."
    return None


def _check_read(file_path: str) -> str | None:
    """Return a block reason for a Read target, or None to allow."""
    if not file_path:
        return None
    if _SECRET_FILE.search(file_path):
        return (
            f"Blocked: `{file_path}` looks like a secret/.env file; "
            "the guard refuses to read it (CLAUDE.md §15)."
        )
    return None


def evaluate(tool_name: str, tool_input: dict) -> str | None:
    """Pure decision function. Returns a block reason, or None to allow."""
    if tool_name == "Bash":
        return _check_bash(str(tool_input.get("command", "")))
    if tool_name in ("Read", "Edit", "Write", "NotebookEdit"):
        return _check_read(str(tool_input.get("file_path", "")))
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open: never brick the session on bad input
        print(f"pretool_guard: could not parse hook payload ({exc}); allowing.", file=sys.stderr)
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        return 0

    try:
        reason = evaluate(tool_name, tool_input)
    except Exception as exc:  # fail open on guard bugs
        print(f"pretool_guard: guard error ({exc}); allowing.", file=sys.stderr)
        return 0

    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    # Allow forcing fail-open in emergencies without editing the file.
    if os.environ.get("PULSEPRESS_DISABLE_GUARD") == "1":
        sys.exit(0)
    sys.exit(main())
