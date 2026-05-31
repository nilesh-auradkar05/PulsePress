# ADR-0002-cognito-auth-code-pkce — Cognito Auth Code + PKCE

Status: Accepted for Phase 1.

## Context

PulsePress needs real OAuth2/OIDC authentication without building a custom identity system.
The API must validate tokens rigorously, but local development and automated tests must not
require a live AWS Cognito user pool.

## Decision

- **Production auth is Amazon Cognito, Authorization Code + PKCE.** The API validates the JWT's
  RS256 signature against the pool's JWKS, plus `issuer`, `audience`, `exp`, and `token_use`
  (`apps/api/app/auth/jwt.py`). The browser PKCE redirect flow is wired in a later sprint.
- **A local-dev auth shortcut** (`apps/api/app/auth/local.py`, `app/api/router_local.py`) mints and
  verifies HS256 tokens and is mounted **only when `ENVIRONMENT=local`**. It is a separate router,
  **not** part of the product OpenAPI contract (SPEC §9.1, CLAUDE.md §15), so it can never appear in
  the production surface.
- A single `get_current_user` dependency selects the verifier by environment, maps claims to a
  `users` row (just-in-time provisioning on first sight), and raises 401 (rendered as RFC 7807).

## Consequences

- **+** The whole auth-gated API is exercisable locally and in CI with no AWS dependency.
- **+** One code path validates and provisions users regardless of verifier.
- **−** The local shortcut is intentionally insecure (shared HS256 secret, no password check); it is
  guarded by the `ENVIRONMENT=local` gate and excluded from the production app.
- The real Cognito user pool + app client are provisioned by Terraform (`modules/cognito`); the
  browser-side PKCE flow and token storage are deferred to the frontend sprint.
