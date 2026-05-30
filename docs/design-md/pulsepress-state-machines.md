# PulsePress — State Machines (v1.2)

## Post

`draft → published → archived`

- Draft and published edits are CRUD self-loops and emit no events.
- `publishPost` is state-level idempotent and emits `post.published` exactly once.
- Archive is a soft-delete transition. No republish in Phase 1.

## Subscription

`active → canceled → expired`

- `subscribe()` creates active subscription and emits `subscription.created`.
- Free and paid subscriptions both require `Idempotency-Key`.
- Tier change is an active self-loop: immediate `plan_id` + `amount_cents` update, emits `subscription.tier_changed`, no ledger in Phase 1.
- Cancel emits `subscription.canceled`; access remains until `period_end`.
- Expired is lazily derived; no scheduler and no `subscription.expired` event.

## Gift

`pending → processed | failed`

- Gift send emits `gift.sent`.
- Worker records ledger and marks processed.
- Admin retry can move failed back to pending.
