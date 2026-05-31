"""Local-dev auth shortcut: mint/verify HS256 tokens.

Used only when ``ENVIRONMENT=local`` so the frontend (and tests) can exercise
the auth-gated API without a live Cognito user pool. The token shape mirrors a
Cognito ID token closely enough for ``get_current_user`` to map claims to a user.
"""

from __future__ import annotations

import datetime
from typing import Any

import jwt
from jwt import InvalidTokenError

from app.auth.jwt import TokenError
from app.core.config import settings

DEFAULT_TTL = datetime.timedelta(hours=12)


def mint_local_token(*, sub: str, email: str | None, name: str) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "name": name,
        "token_use": "id",
        "iat": now,
        "exp": now + DEFAULT_TTL,
    }
    return jwt.encode(payload, settings.local_jwt_secret, algorithm=settings.jwt_algorithm_local)


def verify_local_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.local_jwt_secret,
            algorithms=[settings.jwt_algorithm_local],
        )
    except InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc
