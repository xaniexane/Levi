# The Money Law

**Binding law (Chauncey, 2026-09-17): Cybrus is the only one ever allowed
to handle money.** No other founder, agent, or module moves money except
through the Cybrus money gateway (`core/levi/cybrus/money.py`).

## Audit findings (2026-09-17)

Sweep of the full repo for money paths. **Result: zero live money
paths exist; zero bypasses of Cybrus.** Every money-adjacent module is
honestly non-executing:

| Path | What it does | Bypasses Cybrus? |
|---|---|---|
| `finance/` (broker, portfolio, bets, brokerlink) | Paper/simulated trading; live trading **structurally disabled** (`LEVI_BROKER_LIVE` unset, no transport wired, per-order explicit confirmation required; `brokerlink.execute_live` raises unconditionally) | No — no live path exists |
| `monetize/projects/*` (12 modules) | Quote/invoice **drafting** only — "no charge, no contact"; payment is Chauncey-confirmed; "Chauncey sends it; payment must land first" | No — drafts, not charges |
| `monetize/ledger.py` | Append-only income **event** ledger at `~/.levi/monetize/income.jsonl` — records, never moves | No |
| `neighbor/pay.py` + `neighbor/monetize.py` | Settlement **ledger** (who owes whom) + fee **math**; real money movement explicitly lives in "labeled external plug-ins — references, never core" | No |
| `income/factory.py` | Service **plan** drafts — "never auto-charges money"; HITL before payment | No |
| `king/ledger.py` | Word-count/rank continuity ledger — not money at all | No |
| `cloud/metering.py` | Usage metering — "no billing attached... no payment rails by design" | No |
| `daemon/kernel.py charge()` | Internal compute-unit budget accounting | No |
| `governor/priority.py refund()` | Internal burst-pass accounting | No |
| `revival/` money-named modules (carrier_billing, carrier_micropay, creator_economics, kiosk, paid_community, metered_viewdata, indie_channel, …) | Local-ledger accounting sims, all explicitly documented "no real payments, no network" / "ledgered, not settled" | No |
| `advisor/pricing.py` | Price **advice** only — advises, never transacts; no network, no SDKs | No |
| Payment SDK imports (stripe, paypal, square, braintree) | **Zero hits anywhere in the repo** | N/A |

No payment plug-ins exist in `core/levi/plugins/` either (catalog, cli,
github, http, references, registry, rss, social_stub — none payment).

## The gateway

`core/levi/cybrus/money.py` — `MoneyGateway` is the single choke point.
Any future money movement must call through it. It fails CLOSED:

- `plan()` — six-gate PLAN: computes what a movement *would* look like,
  moves nothing.
- `preview()` — six-gate PREVIEW: human-readable statement.
- `authorize()` — six-gate PERMISSION: explicit Chauncey authorization
  for one plan; anything else refuses.
- `execute()` — six-gate EXECUTE: refuses unless a rail is registered
  AND authorized. With no rails registered (current state), **always
  refuses** (`NoRailConfigured`).
- `verify()` / `receipt()` — six-gate VERIFY + RECEIPT over the audit trail.

A rail is a REFERENCE to an external payment plug-in, never the plug-in
itself. Rails are registered deliberately by Chauncey only
(`register_rail` refuses non-keeper approvers). No rails exist yet; no
plug-ins exist yet.

Audit: every plan/authorize/execute attempt is logged (metadata only —
never secrets) to `~/.levi/cybrus/money/money_audit.jsonl`, owner-only
`0o600`.

## Enforcement

`tests/test_money_law.py` enforces the law structurally:

1. No payment-SDK imports outside `core/levi/cybrus/`.
2. Any money-verb function def outside `core/levi/cybrus/` must carry an
   explicit `ACCOUNTING_ALLOWLIST` entry with an honest reason; silent
   money verbs fail the suite.
3. Finance stays paper-only (`live_enabled()` False; `execute_live` raises).
4. The gateway fails closed (plan/preview OK; authorize/execute refuse
   without keeper + rail; audit records every attempt).

CLI: `levi cybrus money status|rails|audit`.

## Honest limits

- The gateway is a choke point and a fail-closed scaffold, not a payment
  processor: no provider calls, no real rails, no plug-ins exist.
- The guard test is static: it catches SDK imports and money-verb defs,
  not cleverly obfuscated exfiltration. It is a tripwire, not a proof.
- Adding a real rail is a deliberate Chauncey-gated act, not an
  automation target.
