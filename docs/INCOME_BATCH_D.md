# Income Batch D — Data Products (slots 61–72)

Twelve original automated income generators (`core/levi/income/gen_data.py`),
each building a real local data product from user-supplied input (params) or a
bundled deterministic sample fixture. Stdlib only. No network, no paid APIs,
no third-party code, no scraping. Every line original.

Each generator writes real artifacts (CSVs + a human-readable report/plan) to
`<levi_home>/.levi/income/work/<id>/` on a real run, and reports what it
*would* write on a dry run (dry runs touch no deliverable files).

Money law: `run()` returns a `WorkReport` with `quoted_amount_usd` — pricing
advice only. Income is recorded solely by Chauncey via
`engine.record_income(..., basis="confirmed")`. Nothing here invents income.

## The twelve

| Slot | ID | Entry | What it builds |
|------|----|-------|----------------|
| 61 | `habit-tracker-kit` | $3 | Habit-tracking CSV + streak summary (current/longest streaks, completion rate, on-pace vs weekly target) from a habit list |
| 62 | `budget-ledger-builder` | $2 | Zero-based budget ledger: income/expenses assigned line by line, remainder auto-assigned to savings, pass/fail balance check |
| 63 | `price-watchlist` | $3 | Manual-entry price tracker (no scraping): per-item trends, lows/highs, drop-% and below-target alerts |
| 64 | `reading-log-atlas` | $2 | Reading log CSV + stats: pace (pages/day), genre breakdown with avg ratings, currently-reading shelf |
| 65 | `workout-planner-pack` | $4 | Workout plans from goal/equipment/days-per-week: session rotation, sets×reps, weekly progression notes |
| 66 | `meal-prep-planner` | $4 | Weekly meal plan + grocery list from pantry inputs: recipes ranked by pantry overlap, diet filters, cost estimate |
| 67 | `invoice-aging-tracker` | $5 | AR aging buckets (current/1–30/31–60/61–90/90+) with a prioritized follow-up list and per-client rollups |
| 68 | `content-calendar-forge` | $3 | 30-day content calendar from theme inputs: round-robin themes × channels × formats with working titles |
| 69 | `kpi-dashboard-text` | $4 | Text-mode KPI dashboard: latest values, 7-day/span deltas, min/max/avg, trend verdicts, ASCII sparklines |
| 70 | `survey-tally-engine` | $2 | Survey tallies: ranked frequencies, consensus verdict; mean/median for numeric scale questions |
| 71 | `inventory-ledger-kit` | $5 | Small-business inventory tracker: stock status vs reorder points, suggested order quantities, inventory valuation |
| 72 | `subscription-auditor` | $3 | Finds forgotten subscriptions in a manually-imported statement CSV: recurring detection, cadence, monthly burn, yearly projection |

## What each earns (pricing advice)

Entry prices follow the founder doctrine (no free core, entry $1–5, ~30–60%
below the giants). The quoted amount is what a single build/run of that data
product is worth as a one-off product sale; recurring use (weekly meal plans,
monthly AR aging, ongoing habit tracking) is the natural upsell path, priced
per the advisor at sale time. The 70/30 split applies when Chauncey confirms
an income event.

## Params (user inputs)

Every generator accepts its inputs through `params` (see module docstrings and
`tests/test_income_data.py` for shapes); omitting them runs the bundled sample
fixture so the product is demonstrable with zero setup. Useful anchors:
`end`/`start`/`as_of` take `YYYY-MM-DD` for deterministic windows.

## Tests

`tests/test_income_data.py` — 31 tests: registry presence (12 ids, slots
61–72, kind `data-product`), per-generator dry-run + real run smoke, dry-run
file safety, $1–5 price bounds, and params paths (budget ledger, invoice aging,
subscription detection, survey numerics, KPI sparklines).
