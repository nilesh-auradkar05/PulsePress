"""Subscription API routes (create, get, change tier, cancel).

Money-shaped writes delegate to ``app.services.commerce``; this layer only maps
HTTP concerns: the ``Idempotency-Key`` header, the request correlation id, the
response status, and the ``Idempotency-Replayed`` header.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models import Subscription, User
from app.schemas.commerce import (
    SubscriptionCreate,
    SubscriptionOut,
    SubscriptionResult,
    SubscriptionTierChange,
)
from app.services import commerce
from app.services.commerce import CommerceResult

router = APIRouter(prefix="/v1", tags=["subscriptions"])

DbSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "") or ""


def _apply(result: CommerceResult, response: Response) -> dict:
    response.status_code = result.status_code
    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return result.body


@router.post(
    "/subscriptions",
    response_model=SubscriptionResult,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    body: SubscriptionCreate,
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKeyHeader = None,
) -> dict:
    result = commerce.create_subscription(
        db,
        user=current_user,
        body=body,
        idempotency_key=idempotency_key,
        correlation_id=_correlation_id(request),
    )
    return _apply(result, response)


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(
    subscription_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> SubscriptionOut:
    subscription = db.get(Subscription, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    if subscription.subscriber_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own subscription.",
        )
    return SubscriptionOut.model_validate(subscription)


@router.patch("/subscriptions/{subscription_id}", response_model=SubscriptionResult)
def change_tier(
    subscription_id: uuid.UUID,
    body: SubscriptionTierChange,
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKeyHeader = None,
) -> dict:
    result = commerce.change_tier(
        db,
        user=current_user,
        subscription_id=subscription_id,
        body=body,
        idempotency_key=idempotency_key,
        correlation_id=_correlation_id(request),
    )
    return _apply(result, response)


@router.delete("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def cancel_subscription(
    subscription_id: uuid.UUID,
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKeyHeader = None,
) -> dict:
    result = commerce.cancel_subscription(
        db,
        user=current_user,
        subscription_id=subscription_id,
        idempotency_key=idempotency_key,
        correlation_id=_correlation_id(request),
    )
    return _apply(result, response)
