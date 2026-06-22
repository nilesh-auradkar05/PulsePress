"""Subscription-plan API routes (owner-configured tiers).

Plans are commerce *config*, not a money-shaped write: no idempotency key and no
events. Content gating stays binary (free vs paid); higher-priced tiers are
voluntary patronage, not extra access (SPEC §7.2).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models import Publication, SubscriptionPlan, User
from app.schemas.commerce import PlanCreate, PlanOut

router = APIRouter(prefix="/v1", tags=["plans"])

DbSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _active_publication(db: Session, publication_id: uuid.UUID) -> Publication:
    publication = db.get(Publication, publication_id)
    if publication is None or not publication.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    return publication


@router.get("/publications/{publication_id}/plans", response_model=list[PlanOut])
def list_plans(
    publication_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[PlanOut]:
    del current_user
    _active_publication(db, publication_id)
    plans = db.execute(
        select(SubscriptionPlan)
        .where(
            SubscriptionPlan.publication_id == publication_id,
            SubscriptionPlan.is_active.is_(True),
        )
        .order_by(SubscriptionPlan.monthly_price_cents.asc(), SubscriptionPlan.created_at.asc())
    ).scalars().all()
    return [PlanOut.model_validate(plan) for plan in plans]


@router.post(
    "/publications/{publication_id}/plans",
    response_model=PlanOut,
    status_code=status.HTTP_201_CREATED,
)
def create_plan(
    publication_id: uuid.UUID,
    body: PlanCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PlanOut:
    publication = _active_publication(db, publication_id)
    if publication.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the publication owner can create plans.",
        )

    plan = SubscriptionPlan(
        publication_id=publication.id,
        name=body.name,
        monthly_price_cents=body.monthly_price_cents,
        currency=body.currency,
        allow_open_amount=body.allow_open_amount,
        benefits=body.benefits,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return PlanOut.model_validate(plan)
