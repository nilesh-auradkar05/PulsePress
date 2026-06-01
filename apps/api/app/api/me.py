"""Product auth routes (mounted under /v1). Currently: GET /v1/me."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/v1", tags=["auth"])


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
