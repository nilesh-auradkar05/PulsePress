"""PulsePress API service entrypoint.

Sprint 1 is the walking skeleton: only the internal ``/healthz`` endpoint is
mounted. Product endpoints under ``/v1`` (auth, publications, posts, commerce)
arrive in later sprints per docs/sprint-plan.md.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.service_name, version=settings.version)
    app.include_router(health_router)
    return app


app = create_app()
