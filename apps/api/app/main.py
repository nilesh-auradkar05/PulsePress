"""PulsePress API service entrypoint.

Sprint 2 adds authentication: the internal ``/healthz`` probe, the product
``GET /v1/me`` (Cognito Bearer JWT), and — only when ``ENVIRONMENT=local`` — a
local-dev auth shortcut. Errors are RFC 7807 with a propagated correlation id.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.api.me import router as me_router
from app.core.config import settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.problem import http_exception_handler, validation_exception_handler


def create_app() -> FastAPI:
    app = FastAPI(title=settings.service_name, version=settings.version)

    app.add_middleware(CorrelationIdMiddleware)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.include_router(health_router)
    app.include_router(me_router)

    # The local-dev auth shortcut must never exist in the production surface.
    if settings.is_local:
        from app.api.router_local import router as local_auth_router

        app.include_router(local_auth_router)

    return app


app = create_app()
