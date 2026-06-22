"""Smoke test: the worker entrypoint is importable."""

from __future__ import annotations

from pulsepress_worker.main import main


def test_main_is_callable() -> None:
    assert callable(main)
