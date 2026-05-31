"""Production Cognito JWT validation.

Validates RS256 signature (via the pool's JWKS), issuer, audience, expiration,
and ``token_use`` (SPEC §14, CLAUDE.md §15). The pure ``decode_cognito`` step
takes an already-resolved key so it is unit-testable without network access;
``verify_cognito_token`` resolves the signing key from the JWKS first.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient

VALID_TOKEN_USES = ("id", "access")


class TokenError(Exception):
    """Raised when a token fails validation."""


def decode_cognito(token: str, key: Any, *, issuer: str, audience: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
    except InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc
    if claims.get("token_use") not in VALID_TOKEN_USES:
        raise TokenError("invalid token_use claim")
    return claims


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def verify_cognito_token(
    token: str, *, issuer: str, audience: str, jwks_url: str
) -> dict[str, Any]:
    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    except Exception as exc:  # noqa: BLE001 - any JWKS resolution failure is an auth failure
        raise TokenError(f"could not resolve signing key: {exc}") from exc
    return decode_cognito(token, signing_key.key, issuer=issuer, audience=audience)
