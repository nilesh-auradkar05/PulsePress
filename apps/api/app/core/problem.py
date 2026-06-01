"""RFC 7807 Problem Details responses and exception handlers.

All error responses use ``application/problem+json`` and echo the request's
``correlation_id`` (CLAUDE.md §9, SPEC §9.1).
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

PROBLEM_MEDIA_TYPE = "application/problem+json"


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "") or ""


def make_problem(
    *,
    status: int,
    detail: str,
    correlation_id: str,
    title: str | None = None,
    type_: str = "about:blank",
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": type_,
        "title": title or HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "correlation_id": correlation_id,
    }
    if extra:
        body.update(extra)
    headers = {"X-Correlation-Id": correlation_id} if correlation_id else None
    return JSONResponse(
        status_code=status, content=body, media_type=PROBLEM_MEDIA_TYPE, headers=headers
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return make_problem(
        status=exc.status_code,
        detail=str(exc.detail),
        correlation_id=_correlation_id(request),
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    field_errors = [
        {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return make_problem(
        status=422,
        title="Validation Error",
        detail="Request validation failed",
        correlation_id=_correlation_id(request),
        extra={"field_errors": field_errors},
    )
