"""Commerce API schemas (plans, subscriptions, gifts, bill breakdown).

Mirrors the canonical contract in ``docs/openapi.yaml``. All money is integer
cents; currency is USD-only in Phase 1.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BillBreakdown(BaseModel):
    """Transparent itemization. Invariant enforced on ``ledger_transactions``."""

    amount_cents: int = Field(ge=0)
    author_net_cents: int = Field(ge=0)
    platform_fee_cents: int = Field(ge=0)
    tax_cents: int = Field(ge=0)
    total_charged_cents: int = Field(ge=0)


# --- Plans ----------------------------------------------------------------


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    publication_id: uuid.UUID
    name: str
    monthly_price_cents: int
    currency: str
    allow_open_amount: bool
    benefits: list[str] | None = None
    is_active: bool


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    monthly_price_cents: int = Field(ge=0)
    allow_open_amount: bool = False
    benefits: list[str] | None = None
    currency: Literal["USD"] = "USD"


# --- Subscriptions --------------------------------------------------------


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscriber_user_id: uuid.UUID
    publication_id: uuid.UUID
    plan_id: uuid.UUID
    amount_cents: int
    status: Literal["active", "canceled", "expired"]
    period_start: datetime.datetime
    period_end: datetime.datetime | None = None
    canceled_at: datetime.datetime | None = None
    access_until: datetime.datetime | None = None


class SubscriptionCreate(BaseModel):
    publication_id: uuid.UUID
    plan_id: uuid.UUID
    amount_cents: int = Field(ge=0)


class SubscriptionTierChange(BaseModel):
    new_plan_id: uuid.UUID
    new_amount_cents: int = Field(ge=0)


class SubscriptionResult(BaseModel):
    subscription_id: uuid.UUID
    status: Literal["active", "canceled", "expired"]
    tier: Literal["free", "paid"]
    bill: BillBreakdown | None = None
    period_end: datetime.datetime | None = None


# --- Gifts ----------------------------------------------------------------


class GiftCreate(BaseModel):
    publication_id: uuid.UUID
    amount_cents: int = Field(ge=50, description="Min $0.50")
    message: str | None = Field(default=None, max_length=280)


class GiftResult(BaseModel):
    gift_id: uuid.UUID
    status: Literal["pending", "processed", "failed"]
    bill: BillBreakdown
