"""Domain errors for commerce writes, translated to RFC 7807 in one handler.

Services raise these; ``commerce_error_handler`` (registered in ``app.main``)
renders them as ``application/problem+json`` with the request correlation id.
Keeping HTTP status off the route handlers lets the business logic stay in the
service layer (CLAUDE.md §9).
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.problem import make_problem

_PROBLEM_BASE = "https://pulsepress.example/problems"


class CommerceError(Exception):
    """Base class for commerce domain failures."""

    status_code: int = 400
    problem_type: str = "about:blank"
    title: str | None = None

    def __init__(self, detail: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class IdempotencyKeyRequired(CommerceError):
    status_code = 422
    problem_type = f"{_PROBLEM_BASE}/idempotency-key-required"
    title = "Idempotency-Key required"


class IdempotencyConflict(CommerceError):
    status_code = 422
    problem_type = f"{_PROBLEM_BASE}/idempotency-conflict"
    title = "Idempotency key reused with different body"


class IdempotencyInFlight(CommerceError):
    status_code = 409
    problem_type = f"{_PROBLEM_BASE}/idempotency-in-flight"
    title = "Idempotency key already in use"


class ValidationProblem(CommerceError):
    status_code = 422
    problem_type = f"{_PROBLEM_BASE}/validation"
    title = "Validation failed"

    def __init__(self, detail: str, *, field: str, code: str) -> None:
        super().__init__(detail, extra={"field_errors": [{"field": field, "code": code}]})


class SelfActionForbidden(CommerceError):
    status_code = 403
    problem_type = f"{_PROBLEM_BASE}/self-action"
    title = "Action not allowed on your own publication"


class ForbiddenError(CommerceError):
    status_code = 403
    title = "Forbidden"


class ResourceNotFound(CommerceError):
    status_code = 404
    title = "Not Found"


class DuplicateActiveSubscription(CommerceError):
    status_code = 409
    problem_type = f"{_PROBLEM_BASE}/duplicate-subscription"
    title = "Subscription already active"


class ConflictError(CommerceError):
    status_code = 409
    title = "Conflict"


async def commerce_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, CommerceError)
    correlation_id = getattr(request.state, "correlation_id", "") or ""
    return make_problem(
        status=exc.status_code,
        detail=exc.detail,
        correlation_id=correlation_id,
        title=exc.title,
        type_=exc.problem_type,
        extra=exc.extra,
    )
