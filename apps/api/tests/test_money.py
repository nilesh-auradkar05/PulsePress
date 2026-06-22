"""Money/bill invariant tests (SPEC §7). Pure — no database."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from app.domain import money
from app.domain.money import compute_bill


def test_subscription_example_matches_event_catalog() -> None:
    bill = compute_bill(500, platform_fee_pct=Decimal("0.10"), tax_pct=Decimal("0.08"))
    assert bill.platform_fee_cents == 50
    assert bill.tax_cents == 40
    assert bill.author_net_cents == 450
    assert bill.total_charged_cents == 540


def test_gift_example_matches_event_catalog() -> None:
    bill = compute_bill(1000, platform_fee_pct=Decimal("0.10"), tax_pct=Decimal("0.08"))
    assert (bill.platform_fee_cents, bill.tax_cents) == (100, 80)
    assert (bill.author_net_cents, bill.total_charged_cents) == (900, 1080)


def test_round_half_up_on_fee_and_tax() -> None:
    # 10% of 5c = 0.50 -> rounds up to 1; 8% of 5c = 0.40 -> rounds down to 0.
    bill = compute_bill(5, platform_fee_pct=Decimal("0.10"), tax_pct=Decimal("0.08"))
    assert bill.platform_fee_cents == 1
    assert bill.tax_cents == 0
    assert bill.author_net_cents == 4
    assert bill.total_charged_cents == 5


def test_zero_amount_is_all_zero() -> None:
    bill = compute_bill(0)
    assert bill.as_dict() == {
        "amount_cents": 0,
        "author_net_cents": 0,
        "platform_fee_cents": 0,
        "tax_cents": 0,
        "total_charged_cents": 0,
    }


def test_negative_amount_rejected() -> None:
    with pytest.raises(ValueError):
        compute_bill(-1)


@pytest.mark.parametrize(
    "amount",
    [1, 7, 13, 49, 50, 99, 100, 333, 500, 999, 1000, 1234, 2500, 9999, 123456],
)
def test_invariants_hold_for_many_amounts(amount: int) -> None:
    bill = compute_bill(amount, platform_fee_pct=Decimal("0.10"), tax_pct=Decimal("0.08"))
    entries_total = bill.author_net_cents + bill.platform_fee_cents + bill.tax_cents
    assert entries_total == bill.total_charged_cents
    assert bill.amount_cents + bill.tax_cents == bill.total_charged_cents
    assert min(bill.as_dict().values()) >= 0


def test_money_module_uses_no_floats() -> None:
    """Guard against accidental float arithmetic creeping into money code."""
    source = inspect.getsource(money)
    assert "float(" not in source
    assert ": float" not in source
