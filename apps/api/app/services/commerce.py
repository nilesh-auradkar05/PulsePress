"""Commerce write services (subscribe, change tier, cancel, gift).

Each is a money-shaped write (CLAUDE.md §5.1): it requires an idempotency key and
atomically persists the business row, the idempotency record, and a transactional
outbox event, then commits. The bill is computed once here and carried in the
event payload; the worker (Sprint 4) writes the ledger from that payload. **No
ledger rows are written in the API.**
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.money import compute_bill
from app.models import GiftTransaction, Publication, Subscription, SubscriptionPlan, User
from app.schemas.commerce import (
    BillBreakdown,
    GiftCreate,
    GiftResult,
    SubscriptionCreate,
    SubscriptionOut,
    SubscriptionResult,
    SubscriptionTierChange,
)
from app.services import idempotency, outbox
from app.services.errors import (
    ConflictError,
    DuplicateActiveSubscription,
    ForbiddenError,
    ResourceNotFound,
    SelfActionForbidden,
    ValidationProblem,
)

SUBSCRIPTION_PERIOD = datetime.timedelta(days=30)


@dataclass(frozen=True)
class CommerceResult:
    """A response the route serializes; ``replayed`` sets ``Idempotency-Replayed``."""

    status_code: int
    body: dict
    replayed: bool


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _active_publication(db: Session, publication_id: uuid.UUID) -> Publication:
    publication = db.get(Publication, publication_id)
    if publication is None or not publication.is_active:
        raise ResourceNotFound("Publication not found")
    return publication


def _resolve_tier_and_amount(
    plan: SubscriptionPlan, amount_cents: int
) -> tuple[Literal["free", "paid"], int]:
    """Validate the requested amount against the plan and return (tier, amount)."""
    if plan.monthly_price_cents == 0:
        if amount_cents != 0:
            raise ValidationProblem(
                "Free plans must be subscribed with amount_cents = 0.",
                field="amount_cents",
                code="must_be_zero",
            )
        return "free", 0

    if amount_cents < plan.monthly_price_cents:
        raise ValidationProblem(
            f"amount_cents ({amount_cents}) is below plan minimum "
            f"({plan.monthly_price_cents}).",
            field="amount_cents",
            code="below_minimum",
        )
    if amount_cents > plan.monthly_price_cents and not plan.allow_open_amount:
        raise ValidationProblem(
            "This plan does not allow paying above the listed price.",
            field="amount_cents",
            code="open_amount_not_allowed",
        )
    return "paid", amount_cents


def create_subscription(
    db: Session,
    *,
    user: User,
    body: SubscriptionCreate,
    idempotency_key: str | None,
    correlation_id: str,
) -> CommerceResult:
    fingerprint = {"op": "create_subscription", **body.model_dump(mode="json")}
    claimed = idempotency.claim(db, user_id=user.id, key=idempotency_key, request=fingerprint)
    if isinstance(claimed, idempotency.Replay):
        return CommerceResult(claimed.status_code, claimed.body, replayed=True)
    record = claimed

    publication = _active_publication(db, body.publication_id)
    if publication.owner_user_id == user.id:
        raise SelfActionForbidden(
            "A publication owner cannot subscribe to their own publication."
        )

    plan = db.get(SubscriptionPlan, body.plan_id)
    if plan is None or not plan.is_active or plan.publication_id != publication.id:
        raise ResourceNotFound("Plan not found for this publication.")

    tier, amount_cents = _resolve_tier_and_amount(plan, body.amount_cents)

    already_active = db.execute(
        select(Subscription.id).where(
            Subscription.subscriber_user_id == user.id,
            Subscription.publication_id == publication.id,
            Subscription.status == "active",
        )
    ).first()
    if already_active is not None:
        raise DuplicateActiveSubscription(
            "You already have an active subscription to this publication. "
            "Use PATCH to change tier."
        )

    now = _utcnow()
    period_end = now + SUBSCRIPTION_PERIOD
    subscription = Subscription(
        subscriber_user_id=user.id,
        publication_id=publication.id,
        plan_id=plan.id,
        amount_cents=amount_cents,
        charged_amount_cents=amount_cents,
        charged_currency=plan.currency,
        status="active",
        period_start=now,
        period_end=period_end,
    )
    db.add(subscription)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateActiveSubscription(
            "You already have an active subscription to this publication. "
            "Use PATCH to change tier."
        ) from exc

    bill = compute_bill(amount_cents) if tier == "paid" else None
    outbox.enqueue_event(
        db,
        aggregate_type="subscription",
        aggregate_id=subscription.id,
        event_type="subscription.created",
        correlation_id=correlation_id,
        payload={
            "subscription_id": str(subscription.id),
            "subscriber_user_id": str(user.id),
            "publication_id": str(publication.id),
            "plan_id": str(plan.id),
            "amount_cents": amount_cents,
            "currency": plan.currency,
            "tier": tier,
            "period_start": now.isoformat(),
            "period_end": period_end.isoformat(),
            "bill": bill.as_dict() if bill else None,
        },
    )

    body_out = SubscriptionResult(
        subscription_id=subscription.id,
        status="active",
        tier=tier,
        bill=BillBreakdown(**bill.as_dict()) if bill else None,
        period_end=period_end,
    ).model_dump(mode="json")
    idempotency.record_response(record, status_code=201, body=body_out)
    db.commit()
    return CommerceResult(201, body_out, replayed=False)


def change_tier(
    db: Session,
    *,
    user: User,
    subscription_id: uuid.UUID,
    body: SubscriptionTierChange,
    idempotency_key: str | None,
    correlation_id: str,
) -> CommerceResult:
    fingerprint = {
        "op": "change_tier",
        "subscription_id": str(subscription_id),
        **body.model_dump(mode="json"),
    }
    claimed = idempotency.claim(db, user_id=user.id, key=idempotency_key, request=fingerprint)
    if isinstance(claimed, idempotency.Replay):
        return CommerceResult(claimed.status_code, claimed.body, replayed=True)
    record = claimed

    subscription = db.get(Subscription, subscription_id)
    if subscription is None:
        raise ResourceNotFound("Subscription not found")
    if subscription.subscriber_user_id != user.id:
        raise ForbiddenError("You can only change your own subscription.")
    if subscription.status != "active":
        raise ConflictError("Only an active subscription can change tier.")

    plan = db.get(SubscriptionPlan, body.new_plan_id)
    if plan is None or not plan.is_active or plan.publication_id != subscription.publication_id:
        raise ConflictError("Target plan is inactive or not part of this publication.")

    tier, amount_cents = _resolve_tier_and_amount(plan, body.new_amount_cents)

    old_plan_id = subscription.plan_id
    old_amount_cents = subscription.amount_cents
    now = _utcnow()
    subscription.plan_id = plan.id
    subscription.amount_cents = amount_cents

    outbox.enqueue_event(
        db,
        aggregate_type="subscription",
        aggregate_id=subscription.id,
        event_type="subscription.tier_changed",
        correlation_id=correlation_id,
        payload={
            "subscription_id": str(subscription.id),
            "subscriber_user_id": str(user.id),
            "publication_id": str(subscription.publication_id),
            "old_plan_id": str(old_plan_id),
            "new_plan_id": str(plan.id),
            "old_amount_cents": old_amount_cents,
            "new_amount_cents": amount_cents,
            "changed_at": now.isoformat(),
        },
    )

    # Tier change has no new ledger impact in Phase 1, so no bill is charged.
    body_out = SubscriptionResult(
        subscription_id=subscription.id,
        status="active",
        tier=tier,
        bill=None,
        period_end=subscription.period_end,
    ).model_dump(mode="json")
    idempotency.record_response(record, status_code=200, body=body_out)
    db.commit()
    return CommerceResult(200, body_out, replayed=False)


def cancel_subscription(
    db: Session,
    *,
    user: User,
    subscription_id: uuid.UUID,
    idempotency_key: str | None,
    correlation_id: str,
) -> CommerceResult:
    fingerprint = {"op": "cancel_subscription", "subscription_id": str(subscription_id)}
    claimed = idempotency.claim(db, user_id=user.id, key=idempotency_key, request=fingerprint)
    if isinstance(claimed, idempotency.Replay):
        return CommerceResult(claimed.status_code, claimed.body, replayed=True)
    record = claimed

    subscription = db.get(Subscription, subscription_id)
    if subscription is None:
        raise ResourceNotFound("Subscription not found")
    if subscription.subscriber_user_id != user.id:
        raise ForbiddenError("You can only cancel your own subscription.")

    # First cancellation transitions and emits; a later call is a 200 no-op.
    if subscription.status == "active":
        now = _utcnow()
        subscription.status = "canceled"
        subscription.canceled_at = now
        subscription.access_until = subscription.period_end
        access_until = subscription.access_until
        outbox.enqueue_event(
            db,
            aggregate_type="subscription",
            aggregate_id=subscription.id,
            event_type="subscription.canceled",
            correlation_id=correlation_id,
            payload={
                "subscription_id": str(subscription.id),
                "subscriber_user_id": str(user.id),
                "publication_id": str(subscription.publication_id),
                "canceled_at": now.isoformat(),
                "access_until": access_until.isoformat() if access_until else None,
            },
        )

    db.flush()
    body_out = SubscriptionOut.model_validate(subscription).model_dump(mode="json")
    idempotency.record_response(record, status_code=200, body=body_out)
    db.commit()
    return CommerceResult(200, body_out, replayed=False)


def send_gift(
    db: Session,
    *,
    user: User,
    body: GiftCreate,
    idempotency_key: str | None,
    correlation_id: str,
) -> CommerceResult:
    fingerprint = {"op": "send_gift", **body.model_dump(mode="json")}
    claimed = idempotency.claim(db, user_id=user.id, key=idempotency_key, request=fingerprint)
    if isinstance(claimed, idempotency.Replay):
        return CommerceResult(claimed.status_code, claimed.body, replayed=True)
    record = claimed

    publication = _active_publication(db, body.publication_id)
    if publication.owner_user_id == user.id:
        raise SelfActionForbidden("You cannot gift to your own publication.")

    bill = compute_bill(body.amount_cents)
    gift = GiftTransaction(
        sender_user_id=user.id,
        publication_id=publication.id,
        amount_cents=body.amount_cents,
        message=body.message,
        status="pending",
    )
    db.add(gift)
    db.flush()

    outbox.enqueue_event(
        db,
        aggregate_type="gift",
        aggregate_id=gift.id,
        event_type="gift.sent",
        correlation_id=correlation_id,
        payload={
            "gift_id": str(gift.id),
            "sender_user_id": str(user.id),
            "publication_id": str(publication.id),
            "amount_cents": body.amount_cents,
            "currency": gift.currency,
            "message": body.message,
            "bill": bill.as_dict(),
        },
    )

    body_out = GiftResult(
        gift_id=gift.id,
        status="pending",
        bill=BillBreakdown(**bill.as_dict()),
    ).model_dump(mode="json")
    idempotency.record_response(record, status_code=201, body=body_out)
    db.commit()
    return CommerceResult(201, body_out, replayed=False)
