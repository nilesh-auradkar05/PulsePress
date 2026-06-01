"""Local-dev auth router (mounted only when ENVIRONMENT=local).

Simulates Cognito sign-up/sign-in so the frontend can be exercised end-to-end
locally. Each user gets a synthetic ``cognito_sub`` of ``local:<email>``. This
router is NOT part of the product OpenAPI contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.local import mint_local_token
from app.db.session import get_session
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/local/auth", tags=["local-auth"])


def _sub_for(email: str) -> str:
    return f"local:{email.strip().lower()}"


def _token_response(user: User) -> TokenResponse:
    token = mint_local_token(sub=user.cognito_sub, email=user.email, name=user.display_name)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_session)) -> TokenResponse:
    sub = _sub_for(body.email)
    existing = db.execute(select(User).where(User.cognito_sub == sub)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    user = User(cognito_sub=sub, email=body.email, display_name=body.display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_session)) -> TokenResponse:
    sub = _sub_for(body.email)
    user = db.execute(select(User).where(User.cognito_sub == sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No such user")
    return _token_response(user)
