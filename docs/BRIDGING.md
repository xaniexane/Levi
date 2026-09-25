# BRIDGING — Disagreement-Bridging Legitimacy Layer

**Remix delta.** X's Community Notes runs bridging centrally on X-owned
data; legitimacy flows from the platform's moderation apparatus. LEVI runs
a clean-room implementation locally on user-owned rating data — legitimacy
comes from auditable math, not from a central moderator. The algorithm
itself is public knowledge; the derivation below is written from first
principles, not copied from any implementation.

## The math

Rating matrix `r_un ∈ [-1, 1]` (rater u × note n). Fit:

```
r_un ≈ μ + α_u + β_n + γ_u · δ_n
```

- `μ` — global mean rating
- `α_u` — rater intercept (personal leniency)
- `β_n` — **note helpfulness intercept: the score we report**
- `γ_u` — rater's position on the latent disagreement axis
- `δ_n` — note's position on the disagreement axis

Bridging insight: a note rated +1 by raters with `γ > 0` **and** raters
with `γ < 0` cannot be explained by any single `δ_n` — the product
`γ_u·δ_n` can't be positive for both camps at once. The model is forced
to explain cross-camp agreement through `β_n`. A note loved by one camp
only gets a large `|δ_n|` and a modest `β_n`: factional appeal, not
bridging legitimacy.

Fitting: regularized alternating least squares, closed-form 2×2 ridge
regressions per rater and per note, deterministic hash-based init,
`λ=0.15`, 25 iterations. See module docstring for the full derivation.

## Status labels (heuristics on local data, not platform policy)

- `BRIDGING-HELPFUL` — `β ≥ 0.25` with positive raters on both camps
- `HELPFUL-ONE-CAMP` — `β ≥ 0.25` but no cross-camp evidence
- `NOT-HELPFUL` — `β ≤ −0.25`
- `NEEDS-MORE-RATINGS` — fewer than 3 ratings, or weak signal

## CLI

```
python -m levi.bridging note --text "claim to be rated" [--id n1]
python -m levi.bridging rate --note n1 --rater alice --value 1
python -m levi.bridging notes        # bridging scores + status
python -m levi.bridging explain n1   # β, δ, per-rater camps
```

State: `~/.levi/bridging/bridging.json`. The pure function
`fit_bridging(ratings)` is importable without storage — `levi.threads`
reuses it for bridging-ranked discussion trees.

## Honest gaps

- One latent axis is a simplification; real disagreement is
  multi-dimensional.
- Coordinated rating blocs can mimic cross-camp behavior; the math
  detects disagreement patterns, not sincerity.
- Status thresholds are local heuristics. Small local datasets produce
  noisy fits — `NEEDS-MORE-RATINGS` exists for exactly this reason.
