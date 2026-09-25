# Money-law verification: 7 flagged money-verb defs vs the RIGHT guard

Date: 2026-09-22. Agent: 🪙 (money-law surgeon sweep; glyph roster
~/workspace/agent-glyphs.md).

## Mandate

Seven money-verb definitions outside `core/levi/cybrus/` were flagged.
The RIGHT guard (commit 85f4d30d, glyph 🚨) tightened the money path:
account-action gateway, bound expiring grants, human approvals for
sensitive scopes, approval replay/double-spend defenses, credential use
through the vault, mail through the account gateway. Finance stays
PAPER/SIMULATED — this verification checks enforcement plumbing, and
enabled no real-money path.

Per-verb cycle: DIAGNOSE (read the function; does any money movement
route through `levi.cybrus.money.MoneyGateway` / the grant machinery, or
bypass it?) → CONFIRM with evidence, or FIX by routing through the guard.

## Snapshot (pre-work)

- HEAD: `65e7770dbf037069bbb20446916276e235e6d08c`

md5 of every file read (worktree, unchanged by this sweep):

- `core/levi/boards/squares.py` — 237c71eccd3f350f8c4e4d99b4d14165
- `core/levi/builders/economy.py` — 4ef8a63759ee1257f80465d4c66c32b4
- `core/levi/demandpulse/payments.py` — f50f08297b04e43f380c5c40300c0965
- `core/levi/dispatch/checkcalls.py` — dfb819d1a1d4bf7aa6cd2fff2d69d50c
- `core/levi/genex/ledger.py` — ff510ca6c2667f62701c89a43ca273a4
- `core/levi/methods/eniac.py` — 4932af04b44b2902b3422e9d0aa779a1
- `core/levi/suprastreet/commerce.py` — fd7d479d75ce222879ae21640dd8928f
- `core/levi/cybrus/money.py` — b618348f7e53b47913b4bec305a4b7f5
- `core/levi/cybrus/gateway.py` — c7315ebae4b7f6e91a8d934c99d69c1f
- `core/levi/cybrus/approval.py` — a244f2795eb62d3480e0ed7d2d7944f3

## Verdicts — all seven CONFIRMED (no fix needed)

None of the seven moves money; none bypasses the RIGHT guard because
there is no movement to gate. Verified by source read + independent
pytest re-runs (below). Each carries its MONEY LAW comment at the def
(pinned by `tests/test_money_law_seven.py::test_money_law_comments_present_at_all_seven_defs`).

| # | verb | diagnosis | verdict |
|---|------|-----------|---------|
| 1 | `boards/squares.py:withdraw_testimonial` | Withdraws a signed TEXT testimonial from local JSON. The record has no amount/cents fields; author-only retraction gate. No currency, no rails, nothing moves. | CONFIRM — not a money movement. |
| 2 | `builders/economy.py:collect_payment` | Fail-closed stub: every call raises `OwnerGateRequired` before anything could move; the hook point is named, the owner gate visible. Adjacent `marketplace_royalty()` is pure math. | CONFIRM — fails closed; nothing to route. |
| 3 | `demandpulse/payments.py:charge` | Fail-closed stub: always raises `PaymentNotAuthorized`; `PAYMENT_PROCESSOR is None`; no processor wired, no charge path exists. | CONFIRM — dark by construction. |
| 4 | `dispatch/checkcalls.py:charge_cents` | Pure arithmetic (`DetentionPolicy.charge_cents`: dwell hours → int cents). Accrual lands in an in-memory `StopRecord` + a notification TEXT ("detention $X accruing"); `detention_due_cents()` sums it. No funds, no rails. | CONFIRM — accounting only. |
| 5 | `genex/ledger.py:transfer` | In-memory hash-chained asset ledger: moves integer unit counters between string identities. No currency, no network, no payout path (no payment-SDK / network imports anywhere in the module). The def's MONEY LAW comment explicitly names `levi.cybrus.money.MoneyGateway` as the route any future real-asset rail must take. | CONFIRM — paper/simulation; future route named. |
| 6 | `methods/eniac.py:transfer_ratio` | A float metric: share of operator-procedure steps transferred to the ENIAC substrate (0.75 in the pin). Naming coincidence, not money. | CONFIRM — not a money movement. |
| 7 | `suprastreet/commerce.py:settlements` | Read-only accessor over the in-memory paper trail; `record_sale` settles royalty splits as paper records (founder 15% / seller 85% in the pin). No rails, no funds move. | CONFIRM for routing. **Paper-ledger INTEGRITY (mutable Settlement/Product objects) is separate and OPEN** — owned by the 🩸 worker's batch A; see OPEN below. Not duplicated here. |

## Test evidence (fresh re-runs, 2026-09-22, TMPDIR=~/workspace/scratch/pytest-tmp)

```
tests/test_money_law_seven.py        — 7-verb BLUE-1 behavioral pins
tests/test_money_law.py              — structural guard (no payment-SDK imports outside
                                       cybrus/, ACCOUNTING_ALLOWLIST incl. the 7 verbs,
                                       finance paper-only, gateway fails closed)
tests/test_suprastreet.py            — commerce paper behavior
tests/test_squares.py, test_boards.py
tests/test_demandpulse_payments.py
tests/test_dispatch_checkcalls.py
tests/test_genex.py
```

**76 passed, 0 failed.**

Note: `tests/test_cybrus_money*.py` does not exist as a file; the money
guard coverage lives in `tests/test_money_law.py`
(`test_money_gateway_fails_closed`).

## OPEN (not mine — reported, not resolved)

- `tests/test_red1_money_law.py` (RED-1, 🩸 batch A owns the fix):
  3 failed / 1 passed as of this sweep. The RED documents a
  paper-accounting integrity break, NOT real-money movement:
  `SupraStreet.settlements()` returns live `Settlement` objects whose
  nested `payouts` dict is mutable despite the frozen dataclass
  (founder earnings rewritten 300 → 999999; `total_distributed()` 1,501,699
  vs gross 2000), and `product()` returns the live `Product` whose
  `shares` list can be rewritten to redirect the next settlement 100% to
  an attacker (founder cut gone). The tests fail by design until the reads
  become immutable snapshots. This sweep deliberately did NOT touch
  `suprastreet/commerce.py` or the RED file, to avoid duplicating or
  conflicting with 🩸's batch A fix.
- Failing evidence sample: `test_payouts_cannot_be_rewritten` —
  `assert None == 300` after split-table rewrite; payouts became
  `{'mallory': 2000}`.

## Law restated

Standing law unchanged: real money moves through
`levi.cybrus.money.MoneyGateway` only, which fails closed with no rails
registered and no Chauncey authorization. All seven verbs stay on the
ACCOUNTING_ALLOWLIST with honest reasons; any future real-money route in
any of them must go through the gateway.

Agent-Glyph: 🪙
