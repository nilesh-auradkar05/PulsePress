#!/usr/bin/env python3
"""Validate that an OpenAPI document parses and has the required top-level shape.

Usage:
    python3 scripts/ci/validate_openapi.py docs/openapi.yaml

Behavior:
- If PyYAML is importable, fully parse the document and assert:
    * top-level `openapi`, `info`, and `paths` keys exist,
    * `openapi` is a 3.x version string,
    * `paths` is a non-empty mapping and every path has at least one operation.
- If PyYAML is NOT available, fall back to a structural line-scan that checks the
  same top-level keys are present, prints an install hint, and still passes/fails
  meaningfully. This keeps the check runnable before any Python venv exists.

Exit codes: 0 = valid, 1 = invalid, 2 = usage/IO error.

Trace: docs/sprint-plan.md S0-T01 verification; CLAUDE.md §9 (OpenAPI is source of truth).
"""

from __future__ import annotations

import sys

_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def _validate_parsed(doc: object) -> int:
    if not isinstance(doc, dict):
        return _fail("document root is not a mapping")
    for key in ("openapi", "info", "paths"):
        if key not in doc:
            return _fail(f"missing required top-level key: {key!r}")
    version = str(doc["openapi"])
    if not version.startswith("3."):
        return _fail(f"unsupported OpenAPI version: {version!r} (expected 3.x)")
    paths = doc["paths"]
    if not isinstance(paths, dict) or not paths:
        return _fail("`paths` is empty or not a mapping")
    for path, item in paths.items():
        if not isinstance(item, dict):
            return _fail(f"path {path!r} is not a mapping")
        if not any(m in _HTTP_METHODS for m in item):
            return _fail(f"path {path!r} has no HTTP operation")
    print(f"OK: OpenAPI {version} parsed; {len(paths)} paths, all with >=1 operation.")
    return 0


def _validate_structural(text: str) -> int:
    print(
        "WARN: PyYAML not installed; running structural fallback only. "
        "Install with `pip install pyyaml` (or `uv add pyyaml`) for full validation.",
        file=sys.stderr,
    )
    lines = text.splitlines()
    top_keys = {ln.split(":", 1)[0] for ln in lines if ln and not ln[0].isspace() and ":" in ln}
    for key in ("openapi", "info", "paths"):
        if key not in top_keys:
            return _fail(f"missing required top-level key: {key!r} (structural scan)")
    print(f"OK (structural): top-level keys present {sorted(top_keys & {'openapi','info','paths'})}.")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0] if argv else 'validate_openapi.py'} <path-to-openapi.yaml>", file=sys.stderr)
        return 2
    path = argv[1]
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        return 2

    try:
        import yaml  # type: ignore
    except Exception:
        return _validate_structural(text)

    try:
        doc = yaml.safe_load(text)
    except Exception as exc:
        return _fail(f"YAML parse error: {exc}")
    return _validate_parsed(doc)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
