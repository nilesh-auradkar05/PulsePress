"""PulsePress API service entrypoint.

Sprint 2 adds authentication: the internal ``/healthz`` probe, the product
``GET /v1/me`` (Cognito Bearer JWT), and — only when ``ENVIRONMENT=local`` — a
local-dev auth shortcut. Errors are RFC 7807 with a propagated correlation id.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.me import router as me_router
from app.api.publishing import router as publishing_router
from app.core.config import settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.problem import http_exception_handler, validation_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.validate_runtime_config()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.service_name, version=settings.version, lifespan=lifespan)

    app.add_middleware(CorrelationIdMiddleware)
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Correlation-Id"],
            expose_headers=["X-Correlation-Id"],
        )
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.include_router(health_router)
    app.include_router(me_router)
    app.include_router(publishing_router)

    # The local-dev auth shortcut must never exist in the production surface.
    if settings.is_local:
        from app.api.router_local import router as local_auth_router

        app.include_router(local_auth_router)

    return app


app = create_app()
