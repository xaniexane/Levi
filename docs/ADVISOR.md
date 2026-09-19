# Advisor — founder-level feature/price advisor

`core/levi/advisor/` — founder-grade extra modules + skill set. The keeper
asks, the founders answer. All local, deterministic, stdlib-only.

## Canon

The advisor **composes the founders, never duplicates them**:

- Demand signal comes from **DemandPulse** — `levi.demand.scoring.score_card`
  (the real five-factor composite) when the analyst supplies all five
  factors, or an analyst-assessed composite with a stated basis.
- Strategic weight comes from **Oracle** — `levi.oracle.weight_goals`
  against the canonical `feature-strategy` (demand evidence .30 /
  strategic fit .30 / doctrine fit .25 / cost efficiency .15).
- Analytics-side context (what the user actually reaches for) belongs to
  the **DemandPulse + Omnipulse + CyberPulse** composite — see
  `docs/INBOX.md`.

A verdict is arithmetic, not prophecy: it describes how an idea aligns
with the stated strategy. It executes nothing, guarantees nothing, and
touches no money.

## Feature advisor (`levi.advisor.features`)

`advise_feature(FeatureIdea(...))` → `FeatureVerdict`:

- `verdict`: **build** | **hold** | **kill**
- `alignment`: Oracle weighted alignment 0..1
- `demand_composite` / `demand_tier`: the DemandPulse signal (or
  `unassessed`)
- `reasons`: every reason, in order — auditable back to inputs

Rules (deterministic, fail-closed):

- **kill** when demand is DemandPulse-"low" (< 50) or doctrine fit <
  0.40.
- **build** when demand is "high" (>= 75) AND Oracle alignment >= 0.70.
- **hold** otherwise — and always when demand is unassessed. The advisor
  never builds on vibes.
- Malformed input raises `FeatureError`. Nothing is guessed.

CLI:

```
levi advise feature "Offline voice notes" --demand 72 --demand-basis "3 users asked this week" --fit 0.8 --cost medium --doctrine 0.9
```

The full five-factor DemandPulse scoring is available through the
Python API (`demand_factors={...}` with `(score, basis)` pairs).

## Price advisor (`levi.advisor.pricing`)

`advise_price(PricePlan(...))` → `PriceAdvice` (low / high / recommended
/ seat cap / commission line / rationale). Binding doctrine, enforced in
code:

- **No free core, ever.** A price of zero is rejected — the free tier is
  dead by the keeper's own hand. Entry is paid-but-tiny: dollar scale
  ($1–$5/mo).
- **~30–60% below the giants.** With a giant reference supplied, the
  band is `giant × 0.40` to `giant × 0.70` — never at or above the
  giant. Without one, bands come from doctrine anchors and the advice
  says so. The advisor never invents a competitor's price.
- **Volume over margin.** `volume` recommends the low end, `margin` the
  high end.
- **Roster law.** Seat caps from the legion roster canon: entry → 19
  (founder seats), standard → 122 (first wave), flagship → 490 (the
  full legion).
- **AI+SI pairing is the product.** Priced per seat/pair, never per
  model call.
- **Founder commission** where applicable: a labeled separate line, never
  hidden inside the price.

CLI:

```
levi advise price --tier entry --giant-price 20 --strategy volume
levi advise price --tier flagship --commission 0.1
```

## Tests

`tests/test_advisor.py` — scoring determinism, doctrine compliance
(never free, never at/above the giant), verdict thresholds, fail-closed
input handling, CLI round-trip.
