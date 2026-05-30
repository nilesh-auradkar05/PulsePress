"""Smoke test: the worker entrypoint imports and runs without error (S1-T01)."""

from __future__ import annotations

from app.main import main


def test_main_runs() -> None:
    # The skeleton main() must complete without raising.
    main()
