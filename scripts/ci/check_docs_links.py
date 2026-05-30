#!/usr/bin/env python3
"""Check that local markdown links resolve to files that exist.

Usage:
    python3 scripts/ci/check_docs_links.py docs CLAUDE.md [more paths...]

Each argument is a markdown file or a directory (scanned recursively for *.md).
For every inline link `[text](target)` the script verifies that local targets
point at an existing file. External links (http/https/mailto/tel), pure `#anchors`,
and empty targets are skipped. A `#fragment` suffix on a local path is stripped
before the existence check (we verify the file, not the heading).

Exit codes: 0 = all local links resolve, 1 = broken link(s) found, 2 = usage error.

Trace: docs/sprint-plan.md S0-T01 verification; CLAUDE.md §2 (read-order docs must link cleanly).
"""

from __future__ import annotations

import os
import re
import sys

_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_SKIP_SCHEME = re.compile(r"^(https?:|mailto:|tel:|#|data:)", re.IGNORECASE)


def _iter_markdown(paths: list[str]) -> list[str]:
    files: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                files.extend(os.path.join(root, n) for n in names if n.endswith(".md"))
        elif os.path.isfile(p):
            files.append(p)
        else:
            print(f"WARN: path not found, skipping: {p}", file=sys.stderr)
    return sorted(set(files))


def _clean_target(raw: str) -> str:
    t = raw.strip()
    if t.startswith("<") and ">" in t:
        t = t[1: t.index(">")]
    # Drop an optional link title:  (path "Title")  /  (path 'Title')
    for q in ('"', "'"):
        idx = t.find(" " + q)
        if idx != -1:
            t = t[:idx]
    return t.strip()


def _broken_links_in(md_path: str) -> list[tuple[int, str]]:
    broken: list[tuple[int, str]] = []
    base = os.path.dirname(md_path)
    try:
        with open(md_path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print(f"WARN: cannot read {md_path}: {exc}", file=sys.stderr)
        return broken

    for lineno, line in enumerate(lines, 1):
        for m in _LINK.finditer(line):
            target = _clean_target(m.group(1))
            if not target or _SKIP_SCHEME.match(target):
                continue
            # Strip a heading fragment for the file-existence check.
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue  # was a pure #anchor
            resolved = path_part if path_part.startswith("/") else os.path.normpath(os.path.join(base, path_part))
            if not os.path.exists(resolved):
                broken.append((lineno, target))
    return broken


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"usage: {argv[0]} <md-file-or-dir> [more...]", file=sys.stderr)
        return 2

    files = _iter_markdown(argv[1:])
    total_broken = 0
    for md in files:
        for lineno, target in _broken_links_in(md):
            total_broken += 1
            print(f"BROKEN: {md}:{lineno} -> {target}", file=sys.stderr)

    if total_broken:
        print(f"FAIL: {total_broken} broken local link(s) across {len(files)} file(s).", file=sys.stderr)
        return 1
    print(f"OK: all local markdown links resolve across {len(files)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
