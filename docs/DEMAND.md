# DemandPulse — `core/levi/demand/`

DemandPulse scores product opportunities from demand signals. It is an
**advisory, hypothesis-labeled** scoring tool — it never claims real
market demand and never invents data.

## Purpose

Turn free-text demand signals into scored, explainable opportunity
cards so Chauncey can compare ideas on a consistent rubric instead of
gut feel.

## Key APIs

- `DemandPulse(path=None)` — persisted at `~/.levi/demand_pulse.json`.
- `scan_seed(text, segment="general") -> DemandSignal` — classify a
  text snippet into a signal (`kind` is always `HYPOTHESIS`).
- `score_opportunity(demand_id, title, demand_score, serviceability, startup_cost)` — the simple 3-factor worth model.
- `score_five_factor(demand_id, title, factors, weights=None, threshold=75.0)` — the five-factor composite model:
  demand .30 / market_size .25 / competition_gap .20 / trend_velocity
  .15 / entry_feasibility .10. Tiers: `high` (≥75), `watch` (50–75),
  `low` (<50).
- `top_score_cards(n=5)`, `top_opportunities(n=5)`, `format_status()`.
- `levi.demand.scoring`: `validate_factors`, `composite_score`,
  `tier_for`, `parse_weights`, `ScoreCard.explain()` (full audit trail).

## CLI usage

```bash
levi demand --scan "I need help scheduling shifts" --title "Shift planner" \
  --five-factor --ff-demand 70 --ff-market 60 --ff-gap 80 \
  --ff-velocity 50 --ff-feasibility 90 \
  --ff-basis "smoke test estimates"

python -m levi.demand --scan "..." --title "..." --five-factor ...   # same surface
levi demand                                  # status
```

## Honest limits

- **Every five-factor value requires a basis note** (`--ff-basis`);
  scoring is refused without one. This is the honesty guardrail —
  numbers must come with a stated reason.
- All scores are hypotheses, advisory only. DemandPulse has no live
  market data; it scores what you tell it, nothing more.
- No network, no paid APIs, stdlib-only. Fits the "free to produce"
  business principle: zero marginal cost per score.
