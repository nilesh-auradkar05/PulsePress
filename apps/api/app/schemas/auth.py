"""Auth request/response schemas for the local-dev auth shortcut.

These back the ``/local/auth/*`` routes that exist only when
``ENVIRONMENT=local`` and are intentionally NOT part of the product OpenAPI
contract (the production flow is Cognito Authorization Code + PKCE).
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.user import UserOut


class RegisterRequest(BaseModel):
    email: str
    display_name: str
    password: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
