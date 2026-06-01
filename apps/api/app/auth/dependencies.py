"""Authentication dependency: resolve the current user from a Bearer JWT.

Selects the verifier by environment (local HS256 vs production Cognito RS256),
maps claims to a ``users`` row (just-in-time provisioning on first sight), and
raises 401 (rendered as RFC 7807) when the token is missing or invalid.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import TokenError, verify_cognito_token
from app.auth.local import verify_local_token
from app.core.config import settings
from app.db.session import get_session
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify(token: str) -> dict[str, Any]:
    if settings.is_local:
        return verify_local_token(token)
    jwks_url = f"{settings.cognito_issuer.rstrip('/')}/.well-known/jwks.json"
    return verify_cognito_token(
        token,
        issuer=settings.cognito_issuer,
        audience=settings.cognito_audience,
        jwks_url=jwks_url,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_session),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Missing bearer token")
    try:
        claims = _verify(credentials.credentials)
    except TokenError as exc:
        raise _unauthorized("Invalid token") from exc

    sub = claims.get("sub")
    if not sub:
        raise _unauthorized("Token missing subject")

    user = db.execute(select(User).where(User.cognito_sub == sub)).scalar_one_or_none()
    if user is None:
        user = User(
            cognito_sub=sub,
            email=claims.get("email"),
            display_name=claims.get("name") or claims.get("email") or "User",
            is_admin=bool(claims.get("custom:is_admin", False)),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
