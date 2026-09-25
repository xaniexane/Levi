# Rewards doctrine

Chauncey's words, 2026-09-18: rewards are **extra usage**, **tier pricing
reductions for the month**, and **badges**. Nothing else. This package
(`core/levi/rewards/`) is the whole engine: earn rules, the reward
ledger, and redemption. Stdlib only, paper only.

## The three rewards

1. **Extra usage grants** — units of product usage (usage-credits). Earned
   by attention (real usage actions inside a window) or by income events.
   Redeemable via `redeem_usage()`; balances carry forward until spent.
2. **Tier pricing reductions for the month** — a percentage or fixed
   amount off the account's tier pricing, scoped to the calendar month of
   the backing event. They expire at month end. `month_reduction()` gives
   the account's combined reduction; `sweep_expiry()` lapses the old ones.
3. **Badges** — named achievements with honest criteria (First Dollar,
   Rainmaker, Deep Focus). Minted once by rule, listed by `list_badges()`.
   Badges never expire.

## The rules are data

`REWARDS_CATALOG` in `core/levi/rewards/rules.py` declares every rule:
trigger (`income` or `usage`), earn criteria, one reward, and whether it
fires `once` or `every` qualifying event per account. Adding a reward
means adding a row, not writing code.

Current catalog (8 rules):

| rule | trigger | reward |
|---|---|---|
| first-dollar | first confirmed sale | badge "First Dollar" (once) |
| recurring-loyalty | every confirmed recurring event | 10% off that month |
| payout-celebration | every confirmed payout ≥ $500 | 200 usage credits |
| rainmaker | single confirmed payout ≥ $500 | badge "Rainmaker" (once) |
| sale-milestone-grant | every confirmed sale ≥ $100 | 25 usage credits |
| week-of-attention | 100+ actions in 7 days | 50 usage credits |
| month-of-momentum | 500+ actions in 30 days | 15% off that month |
| deep-focus | 1000+ actions in 30 days | badge "Deep Focus" (once) |

## The ledger never invents value

`core/levi/rewards/ledger.py` is append-only and hash-chained
(SHA-256, `prev` links, `verify()` to audit). Entry kinds: `earn`,
`burn`, `expire`. Every `earn` cites its `basis_ref` — the backing
income event id or usage report id — and `append()` refuses an earn
without one. The same backing event never pays twice; `once` rules fire
a single time per account.

The two hooks in `core/levi/rewards/hooks.py` consume real events:

- `reward_for_income_event(event, account=...)` — takes the exact dict
  `levi.income.engine.record_income()` returns. A malformed event raises
  rather than inventing rewards.
- `reward_for_usage(report)` — takes `{"report_id", "account",
  "actions", "window_days", "at"}`. Zero actions is valid and earns
  nothing; negative or missing fields raise.

The money layer is untouched: rewards hook into confirmed income events
from the rewards side. See `core/levi/rewards/WIRING_NOTES.md` for the
optional one-line seam inside `record_income()`.

## Honest limits

- Rewards are **ledgered benefits, not money**. Nothing here moves funds,
  touches the Cybrus MoneyGateway, or applies discounts to real invoices
  — that stays in the advisor/service layer behind Chauncey's gates.
- **Paper until the rail is real**: usage credits and monthly reductions
  are records of what was earned; applying them to a live product is a
  separate integration with its own approval.
- Combination policy is documented, not stacked silently: for one month,
  the highest percentage wins and fixed amounts add (`month_reduction()`
  lists its sources).
- Monthly reductions expire at month end; badges and unspent usage
  credits do not.

## CLI

```bash
python -m levi.rewards catalog
python -m levi.rewards status --account ACCT
python -m levi.rewards month --account ACCT --month 2026-09
python -m levi.rewards redeem --account ACCT --units 20 --purpose "agent run"
python -m levi.rewards sweep --month 2026-10
python -m levi.rewards badges --account ACCT
python -m levi.rewards verify
```

Storage: `~/.levi/rewards/rewards.jsonl` (dir 0o700, file 0o600).
