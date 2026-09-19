# Income Portfolio — the 100-slot generator engine

Chauncey's doctrine: 50–100 automated income generators, all original,
unique, pure from-scratch logic. Free to run / self-sufficient at start
(local-first, stdlib, no paid APIs); after upgrades each funds itself.

## The 70/30 law

Every recorded income event splits automatically:

- **70%** — Chauncey's keeper share.
- **30%** — the reinvestment pool (domains, unavoidable APIs — "some
  things you just can't cut").

Pool spends are approved by Chauncey only, and the actual money movement
executes ONLY through the Cybrus MoneyGateway — which is fail-closed
(no rails registered). Allocation is real; movement waits on Chauncey.

## The honesty rule

Generators automate the **work** — they produce real artifacts and return
`WorkReport`s (what was produced + an honest quoted amount). Income events
are recorded ONLY with `basis="confirmed"` — Chauncey confirming money
arrived. The engine never invents income. `record_income` raises on any
other basis.

## Pricing

Generators that sell use the founder price advisor: no free core, entry
$1–$5, ~30–60% below giants, roster-law seat caps. `levi income price
[--giant PRICE]`.

## Registry

100 slots (`core/levi/income/engine.py`). Batches own slot ranges and
register from their own `gen_<batch>.py` modules — no two alike. `levi
income list` shows the portfolio; `levi income run <id>` runs a
generator's cycle (dry-run default, `--apply` for real).

## CLI

- `levi income summary` — generators, events, gross, pool
- `levi income list` — the registered portfolio
- `levi income run <id> [--apply]` — run one generator's cycle
- `levi income run-all [--apply]` — sweep the portfolio
- `levi income record <id> <amount> <kind> --basis confirmed [--counterparty] [--note]`
- `levi income events` — the income ledger
- `levi income pool` — reinvestment-pool balance
- `levi income spend <amount> <purpose> --by chauncey` — approve a pool spend
- `levi income price [--giant PRICE]` — price an entry tier

## State

`~/.levi/income/` (owner-only): `runs.jsonl`, `events.jsonl`, `pool.jsonl`.
Confirmed events also write to the shared monetize ledger
(`~/.levi/monetize/income.jsonl`) with the split noted.

## Honest limits

- No payment rails exist. Income events are records; money moves only
  when Chauncey registers a rail through Cybrus.
- A generator's quoted amount is pricing advice, not revenue.
- `run_all` isolates failures: one bad generator never kills the sweep.
