# Echoverse simulation corpora — provenance

## Full chain (Chauncey's word, 2026-09-22)

```
Echo (the being, Omega's original form)
  -> Echoverse engine (Echo in engine form: derives from Echo, carries Echo's
     nature, but its own thing — not 1:1 identical)
  -> LEVI engine (Grok-made REIM/RIEM version)
  -> LWP engine
```

Training source for the three native brains: the Echoverse engine's
simulations, running hypothesize → simulate → train.

## What these corpora are built from

The Grok-made LEVI engine lineage:
`goals/original-levi-lineage-recovery/files/levi-originals/august-lineage/the_pack/echoverse.py`
(REIM/RIEM recursion + multi-agent simulation, August lineage).

- **REIM** (Forward Recursion Echo Mapping): expand a seed into multiple
  candidate hypothesis paths, score them, prefer the best.
- **RIEM** (Reverse Inverse Echo Mapping): vault negative variants but
  extract their good qualities — never discard the whole branch; carry
  forward what still works.
- **dream()**: multi-cycle REIM expansion — the hypothesize → simulate →
  train loop in engine form.

Each record is one REIM round: a seed hypothesis, its simulation trace
(computed numbers, never invented), the score (PREDICTION CHECK), and the
RIEM salvage (REFINED UNDERSTANDING carries forward what the test proved).
Refuted variants are the vault: kept, labeled, learned from — never deleted.

## What these corpora are NOT from

- NOT the outgoing companion-track module (`core/levi/echoverse/` voyage
  engine, being replaced per Chauncey's 2026-09-22 order — old module goes
  to `stored/`, nothing deleted).
- NOT the LWP engine variant (originals `levi_echoverse.js`, `echoverse.py`,
  `05_ECHOVERSE_MANDELLA_COEXISTENCE.md` not located in the accessible
  corpus as of 2026-09-22).
- NOT Echo the being. NOT scraped/external software text. No external text
  enters the neural training path at all.

## Per-corpus record

| corpus | seed | records | chars | sha256 (truncated) |
|---|---|---|---|---|
| corpus_echoverse_a.jsonl | 101 | 1000 | 889,148 | f6f7f4da2514 |
| corpus_echoverse_b.jsonl | 202 | 1000 | 886,319 | 9b6b38acfe43 |
| corpus_echoverse_c.jsonl | 303 | 1000 | 887,376 | cf1510356a1a |

Held-out sets: `heldout_echoverse_{a,b,c}.jsonl`, 120 records each, seeds
9101/9202/9303, provably disjoint from training (P7).

Every record carries `engine_variant: levi-engine-reim-riem-2026-09-22`
plus the full lineage string. Sidecar `<corpus>.manifest.json` files hold
the same. Generator: `core/levi/brain/train/echoverse_sim.py`. Proof:
`core/levi/brain/train/prove_echoverse.py` (P1–P7 all pass).

## Note on the simulation source (switch recorded, not silent)

Per the 2026-09-22 instruction, these corpora prefer the newly installed repo
module as their simulation source. The installed module
(`core/levi/echoverse/`, glyph 🌀, 2026-09-22) is the Grok-made LEVI engine —
the same REIM/RIEM lineage as `the_pack/echoverse.py` (August original),
adapted to the repo layout, plus the six Grok-named lenses
(minimal/maximal/inverse/constraint/deep/reframe) and the shared
Echoverse×Mandella branch substrate. The old companion-track module was
moved to `stored/2026-09-22-echoverse-companion-track/` (nothing deleted).

Each record carries a `lens` field grounded in `lenses.py` (GROK 5):
- `inverse` — the theory was REFUTED (invert the seed, assume it failed,
  recurse; the refined understanding is the recursion).
- `dream` — all other records (one REIM round inside a `dream()`
  multi-cycle expansion).
