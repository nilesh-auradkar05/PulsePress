"""Gift API route (one-time gift to a publication).

Money-shaped, one-shot. Delegates to ``app.services.commerce``; identical bill
breakdown to a subscription. Minimum amount is enforced by the request schema.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.commerce import GiftCreate, GiftResult
from app.services import commerce

router = APIRouter(prefix="/v1", tags=["gifts"])

DbSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/gifts", response_model=GiftResult, status_code=status.HTTP_201_CREATED)
def send_gift(
    body: GiftCreate,
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    result = commerce.send_gift(
        db,
        user=current_user,
        body=body,
        idempotency_key=idempotency_key,
        correlation_id=getattr(request.state, "correlation_id", "") or "",
    )
    response.status_code = result.status_code
    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return result.body
