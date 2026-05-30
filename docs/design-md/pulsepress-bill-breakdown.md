# PulsePress — Subscription/Gift Bill Breakdown (v1.2)

Given principal amount `P` in integer cents:

- `tax = round_half_up(tax_pct × P)`
- `platform_fee = round_half_up(platform_pct × P)`
- `author_net = P - platform_fee`
- `total_charged = P + tax`

Invariant enforced on `ledger_transactions`:

`author_net_cents + platform_fee_cents + tax_cents = total_charged_cents`

`principal_amount_cents + tax_cents = total_charged_cents`

The worker writes exactly three `ledger_entries`: author, platform, tax.
