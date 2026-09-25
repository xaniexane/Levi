# Wiring notes — connecting rewards to the money layer

The rewards engine lives entirely on its own side (`levi.rewards`).
It never edits the money layer. These notes describe the one-line seams
a future integration would add, and the open question that gates it.

## Seam 1: income events -> rewards

`levi.rewards.hooks.reward_for_income_event(event, account=...)` accepts
the exact dict `levi.income.engine.record_income()` returns (id, at,
generator_id, kind, amount, ...). Inside `record_income()`, after the
event is written to `events.jsonl`, add:

```python
# Rewards seam (optional): earn rules fire on the confirmed event.
try:
    from levi.rewards.hooks import reward_for_income_event
    reward_for_income_event(event, account=counterparty or "house")
except Exception:
    pass  # rewards never block or fail income recording
```

Placement: after `_write_jsonl(_events_path(), event)`, before the
return. The try/except mirrors the existing monetize-ledger compose —
the income event file is canonical; rewards are downstream.

## Seam 2: usage reports -> rewards

`levi.rewards.hooks.reward_for_usage(report)` accepts:

```python
{
  "report_id": "unique id of the report",
  "account": "account the usage belongs to",
  "actions": 142,          # real counted actions, int >= 0
  "window_days": 7,        # the window those actions were counted in
  "at": "2026-09-18T10:00:00Z",
}
```

Whoever aggregates attention/use (daemon turns, bot runs, Legion
sessions) calls this once per report. The same report id never pays
twice (`has_earn_for_basis` dedupes).

## Seam 3: redemption at quote time

When the price advisor quotes a tier price, the service/offering layer
may call `levi.rewards.redeem.month_reduction(account, "YYYY-MM")` and
apply `percent_off` / `amount_off_usd` to the quote. Run
`levi.rewards.redeem.sweep_expiry(current_month)` on a schedule (or at
quote time) so lapsed monthly reductions stop applying.

## Open question (needs Chauncey's word)

Income events carry `counterparty`, not an account id. Who earns the
reward for a sale to a client — the client's account, or the house
account? Until he decides, the seam above passes `counterparty or
"house"` and every earn is fully traceable via `basis_ref` + `account`
in the ledger, so re-attribution later is a data migration, not a
rewrite.

## What this package deliberately does NOT do

- Touch `levi.income.engine`, `levi.cybrus`, or any payment path.
- Move money or apply discounts to real invoices — that stays in the
  advisor/service layer with Chauncey's approval gates.
- Invent rewards: every earn cites `basis_ref` (the backing income event
  or usage report id). `ledger.append("earn", ...)` raises without one.
