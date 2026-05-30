"""PulsePress worker service entrypoint.

Sprint 1 is the walking skeleton: the worker is a deployable, importable
placeholder so its container image builds and CI can lint/typecheck/test it.
The outbox poller and the SQS → EventBridge consume loop arrive in Sprint 4
(see docs/sprint-plan.md S4). For now ``main()`` just logs startup.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("pulsepress.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("pulsepress-worker starting (skeleton; no handlers yet)")


if __name__ == "__main__":
    main()
