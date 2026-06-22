"""The three-way money split (SPEC §7, CLAUDE.md §6).

Pure, side-effect-free, **integer cents only** — never floats. The API computes
the bill once here and carries the result in the commerce event payload; the
worker writes exactly what the event says and must not re-derive this math.

For a principal price ``P``:

- ``tax_cents        = round_half_up(tax_pct * P)``         (added on top, buyer-facing)
- ``platform_fee_cents = round_half_up(platform_pct * P)``  (deducted from author's share)
- ``author_net_cents = P - platform_fee_cents``             (residual, so entries sum exactly)
- ``total_charged_cents = P + tax_cents``

Invariants (verified by tests, enforced as CHECKs on ``ledger_transactions``):

    author_net_cents + platform_fee_cents + tax_cents == total_charged_cents
    principal_amount_cents + tax_cents               == total_charged_cents
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import settings


@dataclass(frozen=True)
class Bill:
    """A computed, balanced three-way split. All fields are integer cents."""

    amount_cents: int
    author_net_cents: int
    platform_fee_cents: int
    tax_cents: int
    total_charged_cents: int

    def as_dict(self) -> dict[str, int]:
        return {
            "amount_cents": self.amount_cents,
            "author_net_cents": self.author_net_cents,
            "platform_fee_cents": self.platform_fee_cents,
            "tax_cents": self.tax_cents,
            "total_charged_cents": self.total_charged_cents,
        }


def _round_half_up(amount_cents: int, pct: Decimal) -> int:
    """Round ``pct * amount_cents`` to whole cents, half away from zero."""
    return int((Decimal(amount_cents) * pct).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_bill(
    amount_cents: int,
    *,
    platform_fee_pct: Decimal | None = None,
    tax_pct: Decimal | None = None,
) -> Bill:
    """Derive the balanced bill for a principal price/gift of ``amount_cents``.

    Percentages default to the flat global config (SPEC §7.1) but are injectable
    so the math is unit-testable in isolation.
    """
    if amount_cents < 0:
        raise ValueError("amount_cents must not be negative")

    platform_fee_pct = settings.platform_fee_pct if platform_fee_pct is None else platform_fee_pct
    tax_pct = settings.tax_pct if tax_pct is None else tax_pct

    tax_cents = _round_half_up(amount_cents, tax_pct)
    platform_fee_cents = _round_half_up(amount_cents, platform_fee_pct)
    author_net_cents = amount_cents - platform_fee_cents
    total_charged_cents = amount_cents + tax_cents

    return Bill(
        amount_cents=amount_cents,
        author_net_cents=author_net_cents,
        platform_fee_cents=platform_fee_cents,
        tax_cents=tax_cents,
        total_charged_cents=total_charged_cents,
    )
