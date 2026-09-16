# DIALS — Sovereign Attention Dials

**Remix delta.** Meta/IG/X/TikTok/YouTube rankers are black boxes whose real
job is ad delivery — the user can never see the weights, let alone edit
them. LEVI inverts the pattern: the weight vector lives in the user's own
data dir (`~/.levi/dials/dials.json`), every ranking decision prints its
per-weight contributions, and chronological order is the sticky default
with weights as opt-in overlays. Affinity is an explicit opt-in list the
user edits; LEVI never infers it from behavior.

## What the giants refuse

- Visible, editable ranking weights (the ranker is the ad engine; showing
  it would expose the auction).
- Chronological as a real default (chronological feeds carry no ad
  targeting surface).
- Affinity without surveillance (their "affinity" is inferred from taps,
  dwell, and graph data you can't audit).

## Data model

Item: `{id, author, timestamp, text, tags}`. Weights: `recency, affinity,
diversity, substance, tag_match` — non-negative floats, normalized by
their sum at scoring time. `score = Σ w_f · f(item) / Σ w`.

## CLI

```
python -m levi.dials add --author NAME --text TEXT [--tags a,b]
python -m levi.dials feed [--limit N]        # chronological (sticky default)
python -m levi.dials rank [--limit N]        # one-shot weighted preview; does not move the dial
python -m levi.dials weights                 # show the whole weight vector
python -m levi.dials set-weight recency 2.0
python -m levi.dials mode weighted|chronological
python -m levi.dials affinity-add NAME       # explicit opt-in
python -m levi.dials affinity-remove NAME
python -m levi.dials pin-tag TAG
python -m levi.dials half-life 12            # recency half-life, hours
python -m levi.dials explain <item-id>       # per-feature values + contributions
```

`explain` is the honesty core: for any item it prints each feature value,
each weight, and each weighted contribution, summing to the final score.

## Honest gaps

- `substance` is a length heuristic, documented as such — not a quality
  claim. A long rant scores higher than a short gem.
- `diversity` is greedy and position-aware; it is not a fairness guarantee.
- No collaborative or cross-user signals exist — ranking is purely local
  to this machine's stream. That is the point, and the limit.
