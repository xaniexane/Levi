# The Genesis NFT: the lifetime one-copy buy as a token

Keeper's canon, 2026-09-18: *the one-time lifetime copies ARE NFTs.* Each
year mints a capped number. He or any generous holder must be able to opt
out their weight in the company and product — and the design must make
value rise for them.

This document is the professional design. Everything in it is paper until
the keeper orders otherwise: no chain, no testnet, no funds, no payments.
The source beside this file (`economics.py`, `ledger.py`, `contract.py`,
`treasury.py`, `simulate.py`) is the design as executable law, with 82
tests holding it.

**Decided 2026-09-18 (the keeper's word):** annual mint cap = **1,000
copies per year minimum**; chain = **Base**; rates **confirmed** at 50/30/20
primary and 7.5% royalties; each year's N banked in writing before mint;
money stays paper — no payment rail, no deployment. A lawyer clears the
first real mint: non-negotiable gate, still standing.

---

## 1. The pattern: one token, one pack

A genesis pack already carries a hash-chained manifest — `pack_id` plus a
final hash over every byte. The token's metadata certifies exactly those
two values. One pack hash yields exactly one token id per series
(`sha256(series:pack)` as a uint256), so counterfeits cannot exist: there
is one token per pack, and the token IS the certificate of the pack's
bytes.

The token is a scarce lifetime license — one-time purchase, the copy yours
forever, transferable on the open market. It is not the organism. The
metadata says so plainly, and the license terms forbid representing the
pack as the full LEVI system.

White-label law holds at the token layer: every token's license descriptor
carries the buyer's business name, and LEVI branding is refused on the
customer-facing surface — the same validation the odd-set assembler
enforces. Genesis packs hold odd agent counts only; the token metadata
refuses even counts at build time.

## 2. The series: a capped mint, once a year

Each annual mint is its own series — `GENESIS-2026`, `GENESIS-2027`, and
so on. The cap is published in the contract at series creation and can
never be raised afterwards; it may only be lowered before the first mint,
and never below what already minted. A closed series is never re-minted.
Earlier series stay scarcer forever — that permanence is what lets the
market price them.

The keeper sets N every year, in writing, before mint — and the writing is
now a banked record, not a note. `ledger.py` (`SeriesLedger`) holds each
year's `{year, N, decided_by, decided_at}` as a hash-chained record. The
gate is mechanical: **a series cannot mint until its year's N is
ledgered**, and the published cap must equal the banked N. N below 1,000
is refused unless the keeper's explicit override is flagged on the record
itself — a sub-floor year can never pass silently. Each year records once:
a published N is law, never re-decided.

**The keeper's floor: 1,000 copies per year, minimum** (decided 2026-09-18,
his words: "a thousand at least"). His reasoning: billions of people
worldwide — so a thousand copies stay scarce enough to be valuable, and
still sell enough to be very profitable. Scarcity is the value; volume is
the profit; a thousand holds both.

The framework is `price × quantity = revenue target`, with the standing
guidance: year one starts at the floor — 1,000 — unless the keeper banks a
higher N in writing. N only grows as the buyback treasury proves it can
defend the floor it posts.

## 3. The money: 50 / 30 / 20, and 7.5% forever

Every primary sale splits gross revenue three ways, in code, exact to the
cent — the same enforcement discipline as the 70/30 income split:

- **50% keeper** — his share of the sale.
- **30% pool** — the standing pool allocation, canon untouched.
- **20% buyback treasury** — carved from the keeper's share. The keeper
  funds the exit door himself; that is what makes buyers trust it.

Twenty percent is the recommendation, and the reason is structural: a
primary cut can never lift backing above mint price on its own — each new
token adds only `cut × mint` to the treasury while adding one to supply —
so the cut's job is to make the mint-price floor *credible* from primary
revenue alone in year one, before any secondary volume exists. The keeper **confirmed** the rate 2026-09-18 — it is no longer a recommendation.

Every secondary sale pays a **7.5% royalty** (EIP-2981) straight to the
series' treasury. Inside the 5–10% market norm: heavy enough to feed the
treasury meaningfully, light enough not to chill the secondary market. The
royalty is the growth engine — the only recurring inflow against a capped,
shrinking supply.

## 4. The treasury: the exit door

Per series, the treasury posts a standing floor bid per token:

```
floor = max(mint_price, treasury_balance / outstanding_supply)
```

The invariant that makes it honest: when the floor equals full backing,
every buyback at the floor leaves backing-per-token *unchanged* — the bid
is exactly solvent by construction, proven in the test suite to the cent.
When backing sits below mint price (early, thin treasury), the floor rests
on mint price and buybacks draw down faster than the invariant — fresh
primary revenue and royalties must refill it. Both regimes are simulated;
neither is hidden.

**Bounded liquidity.** At most 5% of a series' treasury may leave through
buybacks in one settlement epoch — with a minimum of one floor bid, so the
door always opens. Requests beyond the budget wait in a FIFO queue. The
floor is a standing bid with bounded liquidity: never a redemption
guarantee, never a promise of any price. That bound is the mechanical
teeth of the securities-safe framing.

**Burn.** Every buyback burns the token. Supply only shrinks. Each burn
removes one token from the denominator that future royalties compound
against — scarcity does the rising.

**Founder parity.** The keeper's reserve tokens are ordinary tokens: same
floor, same queue, no priority. The treasury cannot tell a founder's token
from any holder's. Parity is structural, not promised — the simulator
proves the keeper queuing behind ordinary holders and settling at the
identical price, in FIFO order.

**Custody: the treasury belongs to the holders (decided 2026-09-18).**
The treasury contract holds all funds, and there is no owner/admin
withdrawal function — not for the keeper, not for anyone. Funds move only
two ways: the defined funding inflows (the 20% primary cut, the 7.5%
royalties, receipted keeper top-ups) and the buyback settlement path
(floor bids to exiting holders, token burned on exit). The interface spec
carries no `withdraw`, no `sweep`, no drain — the absence is itself the
law, and conformance fails any deployment whose spec declares a drain
door. The keeper's own exit is bound the same way: his reserve settles
only through the FIFO queue at identical prices. No backdoor, no separate
path. Even the keeper cannot withdraw. His rationale, in his framing: the
floor is a mechanism, not a promise — if he held the keys, buyers would
have to trust him not to drain their exit door, and trust is not a
mechanism.

**Where the rise comes from.** The floor rises when royalty compounding
outruns supply — proven on paper: a sold-out 100-cap series at $50, after
secondary volume, posts a floor of $55, then $62.89, never falling. Three
forces ratchet it: royalties with no new supply, burns shrinking the
denominator, and the keeper's discretionary top-ups (receipted, sourced,
never silent). What the company will not do is promise the rise — see §6.

**The honest boundary.** A mint-price floor over a thin backing is not
fully fundable for every holder at once — no treasury on earth honors a
total run. Under stress the design drains FIFO, one bounded epoch at a
time, never pays what it does not hold, never goes negative, and every
receipt stays verifiable. The queue waits for new inflow. That limit is
the design, not a bug, and it is stated here so no buyer is surprised by
it.

## 5. The contract: specified, not deployed

`contract.py` carries the chain-agnostic interface spec: the eight
functions a conforming deployment must expose (`createSeries`, `mint`,
`burn`, `royaltyInfo`, `seriesOf`, `seriesSupply`, `seriesCap`,
`seriesFloor`), the invariants it must hold (cap never raised, supply
within cap, burned ids never re-minted, royalties exact to the treasury,
epoch outflow bounded), and the reference rule implementations it must
match. A conformance suite runs those invariants over any model ledger.

**Chain: Base — decided 2026-09-18.** The keeper approved the recommendation. Mints cost cents, not dollars — the law
is dollar-scale entry, volume over margin, and L1 fees would eat a
low-tier mint whole. EVM-native ERC-721 + EIP-2981, mature marketplace
royalty support, fiat on-ramps that lower buyer friction in the
small-business lane Legion sells into. Alternatives weighed: Polygon PoS
(cheaper history, sidechain security model) and Solana (lowest fees, but
non-EVM — the spec would need re-idioming). Nothing here deploys, signs, or spends until he orders the rail.

## 6. The law: sold as a license, never as an investment

This is a design constraint, not a footnote. The tokens are sold as scarce
lifetime licenses. The company promises no profit, no yield, and no rising
value. Any secondary-market appreciation is pure market scarcity — the
company does not cause it, direct it, or guarantee it. Marketing must
never claim the token will rise in value, pay returns, or share in company
profits. The moment the sale promises rising value plus payouts from
company revenue, regulators read it as a security — that is the Howey
line, and this design is drawn on the safe side of it deliberately.

**A lawyer clears the first real mint before it happens.** That is not
advice; it is a gate in the design. Until then every figure in this
package is paper.

## 7. What is paper, what is real

Paper: the economics, the treasury math, the scenarios, the contract
spec, every dollar figure. Real: the hash-chained pack manifests the
tokens will certify, the odd-law assembler that builds the packs, the
grade proofs each token carries, the test suite holding the math. The bridge between them — chain pick (decided: Base), annual N (decided: 1,000 floor, yearly in writing), rates (confirmed), legal clearance, payment rail — is the keeper's, in that order.

## 8. Decided, and what stays open

**Decided 2026-09-18 (the keeper's word):**
1. **Chain** — Base, approved.
2. **Annual N** — 1,000 copies per year minimum ("a thousand at least"):
   billions of people worldwide, so a thousand stays scarce enough to be
   valuable and still sells enough to be very profitable. Each year's N is
   banked in writing in the series ledger before mint; N < 1,000 is refused
   without his explicit override on the record.
3. **Rates** — 50/30/20 primary split and 7.5% royalty, confirmed.
4. **Custody** — the buyback treasury belongs to the holders collectively:
   no owner/admin withdrawal function, funds move only via the funding
   inflows and the buyback settlement path; the keeper's own exit settles
   only through the FIFO queue at identical prices. Even the keeper
   cannot withdraw.

**Still open:**
5. **Lawyer** — clears the first real mint. Non-negotiable gate.
6. **Rail** — no payment wiring exists; money stays paper until he orders the rail.

**Proven at the floor (paper):** a ledger-gated, sold-out 1000-cap series
at scenario prices ($50 mint / $100 resales — illustration, not official)
walks its floor $50.00 → $55.00 → $70.15, never falling; ten exits at
full backing leave backing-per-token exactly unchanged ($55.00). The
honest scale note: at N=1000 the crossing needs real secondary volume —
thousands of resales, not hundreds — which is the volume-over-margin lane
doing its work.
