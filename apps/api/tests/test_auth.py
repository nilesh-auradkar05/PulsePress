"""Auth tests (S2-T02): /me gating, local-dev auth flow, prod JWT verifier."""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Iterator

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.auth.jwt import TokenError, decode_cognito
from app.core.config import settings
from app.db.session import get_session
from app.main import create_app

ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/pool"
AUDIENCE = "test-client-id"


@pytest.fixture()
def client(engine: Engine) -> Iterator[TestClient]:
    app = create_app()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override() -> Iterator:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


# --- /me gating -----------------------------------------------------------

def test_me_without_token_is_401_problem(client: TestClient) -> None:
    resp = client.get("/v1/me")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 401
    assert body["correlation_id"]
    assert resp.headers.get("X-Correlation-Id")


def test_me_with_invalid_token_is_401(client: TestClient) -> None:
    resp = client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


# --- local-dev auth flow --------------------------------------------------

def test_register_then_me(client: TestClient) -> None:
    email = _unique_email()
    reg = client.post("/local/auth/register", json={"email": email, "display_name": "Ada"})
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    assert reg.json()["user"]["display_name"] == "Ada"

    me = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["display_name"] == "Ada"
    assert body["email"] == email
    assert body["is_admin"] is False
    assert set(body) >= {"id", "display_name", "is_admin", "created_at"}


def test_register_duplicate_is_409(client: TestClient) -> None:
    email = _unique_email()
    payload = {"email": email, "display_name": "X"}
    assert client.post("/local/auth/register", json=payload).status_code == 201
    dup = client.post("/local/auth/register", json=payload)
    assert dup.status_code == 409


def test_login_unknown_is_401_then_works_after_register(client: TestClient) -> None:
    email = _unique_email()
    assert client.post("/local/auth/login", json={"email": email}).status_code == 401
    client.post("/local/auth/register", json={"email": email, "display_name": "Y"})
    ok = client.post("/local/auth/login", json={"email": email})
    assert ok.status_code == 200
    assert ok.json()["user"]["email"] == email


def test_local_router_absent_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    prod_app = create_app()
    with TestClient(prod_app) as prod_client:
        resp = prod_client.post(
            "/local/auth/register", json={"email": "a@b.com", "display_name": "A"}
        )
    assert resp.status_code == 404


# --- production Cognito verifier (no network; key passed directly) ---------

def _mint_rs256(private_key, **overrides) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": "cognito-sub-1",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "token_use": "id",
        "iat": now,
        "exp": now + datetime.timedelta(hours=1),
    }
    payload.update(overrides)
    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.fixture(scope="module")
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def test_cognito_verifier_happy_path(rsa_keys) -> None:
    private_key, public_key = rsa_keys
    token = _mint_rs256(private_key)
    claims = decode_cognito(token, public_key, issuer=ISSUER, audience=AUDIENCE)
    assert claims["sub"] == "cognito-sub-1"


def test_cognito_verifier_rejects_expired(rsa_keys) -> None:
    private_key, public_key = rsa_keys
    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2)
    token = _mint_rs256(private_key, exp=past)
    with pytest.raises(TokenError):
        decode_cognito(token, public_key, issuer=ISSUER, audience=AUDIENCE)


def test_cognito_verifier_rejects_bad_issuer(rsa_keys) -> None:
    private_key, public_key = rsa_keys
    token = _mint_rs256(private_key, iss="https://evil.example")
    with pytest.raises(TokenError):
        decode_cognito(token, public_key, issuer=ISSUER, audience=AUDIENCE)


def test_cognito_verifier_rejects_bad_audience(rsa_keys) -> None:
    private_key, public_key = rsa_keys
    token = _mint_rs256(private_key, aud="other-client")
    with pytest.raises(TokenError):
        decode_cognito(token, public_key, issuer=ISSUER, audience=AUDIENCE)


def test_cognito_verifier_rejects_bad_token_use(rsa_keys) -> None:
    private_key, public_key = rsa_keys
    token = _mint_rs256(private_key, token_use="nonsense")
    with pytest.raises(TokenError):
        decode_cognito(token, public_key, issuer=ISSUER, audience=AUDIENCE)
