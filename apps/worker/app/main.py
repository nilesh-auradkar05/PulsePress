"""Backward-compatible import path for the worker entrypoint."""

from __future__ import annotations

from pulsepress_worker.main import main

if __name__ == "__main__":
    main()
