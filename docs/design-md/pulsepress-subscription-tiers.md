# PulsePress — Subscription Tiers (v1.2)

Phase 1 supports author-configured tiers with price and soft benefits only.

## Rules

- `monthly_price_cents = 0` means free tier.
- Paid tier means any amount greater than zero.
- Currency is USD only.
- Benefits are `jsonb` display text, not enforced entitlements.
- Content gating is binary: post visibility is `free` or `paid`.
- Any active paid subscription unlocks every paid post for that publication.
- Higher tiers are voluntary support/patronage, not extra content access.

## Explicitly not Phase 1

- Per-tier content gating.
- Proration.
- Auto-renewal.
- Multi-currency.
- Jurisdictional tax.
