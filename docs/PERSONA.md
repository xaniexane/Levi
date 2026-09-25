# PERSONA — affect matrix, hysteresis, blending

The persona nervous system (`core/levi/persona/nervous_system.py`) is a
**local-first, neuro-symbolic control surface** that steers which persona
lens is active. It is not felt emotion: LEVI claims no sentience,
consciousness, or genuine subjective experience. "Affect" here means
*internal load* in the engineering sense — a deterministic regulation
signal, the way a thermostat has a temperature without feeling warm.

## Dimensions

Ten clamped 0..1 axes, one line each:

| dim | definition |
|---|---|
| stress | perceived pressure / intensity of current demands |
| anxiety | uncertainty / ambiguity in the situation |
| workload | density of open tasks and asks |
| energy | momentary available capacity (inverse of acute tiredness) |
| fatigue | accumulated weariness across the session; slow, unlike energy |
| bond | continuity / trust built with this human |
| bond_strain | tension or friction in the bond; rises on hostile cues |
| arousal | short-term activation / alertness |
| valence | pleasant-vs-unpleasant appraisal of the context (PAD) |
| dominance | felt control / capacity relative to demands (PAD) |

`valence / arousal / dominance` are the PAD appraisal model. Roughly:
stress ≈ low valence + high arousal + low dominance;
anxiety ≈ low valence + low dominance; energy/fatigue form arousal's
slow envelope; bond/bond_strain are a relational axis outside PAD.

## Temporal dynamics

Two clocks, not one:

1. **Wall-clock decay** — every `sense()` first relaxes each dimension
   toward its setpoint with its own time constant, computed from
   `updated_at`. Affect settles realistically *between* sessions.

   | dim | tau | setpoint |
   |---|---|---|
   | arousal | 5 min | 0.30 |
   | stress, anxiety | 30 min | 0.25 / 0.20 |
   | workload, energy | 2 h | 0.15 / 0.75 |
   | valence, dominance | 1 h | 0.55 / 0.50 |
   | fatigue | 4 h | 0.12 |
   | bond_strain | 24 h | 0.05 |
   | bond | 3 days | 0.30 |

2. **Per-turn homeostasis** — small multiplicative drift after each
   sensed turn keeps intra-session dynamics smooth (e.g. stress ×0.92,
   arousal ×0.88, energy recovers when stress < 0.35).

Fatigue also accumulates +0.004 per turn (sessions wear); only
wall-clock rest brings it back down.

## Scoring

`score_matrix()` = Σ persona affinity weights × affect + usage momentum
− overuse fatigue + recent-use bonus + gaussian jitter + optional
control-daemon / monotropism biases. Deterministic given a fixed seed.

`explain_scores(top_n)` returns per-persona factor breakdowns whose
values **sum exactly to the reported score**:

```
strategist 0.62: workload×0.50=+0.31, stress×0.35=+0.18, momentum=+0.05, jitter=+0.02…
```

`levi nervous` prints this anatomy for the top 3 personas;
`levi nervous --verbose` dumps the full JSON including the blend.

## Hysteresis (no flapping)

`select()` is a margin-gated argmax, not a softmax sample. The
incumbent keeps its seat unless:

- a challenger beats it by **HYS_MARGIN = 0.06** after holding the seat
  for **HYS_DWELL_MIN = 2** selects, or
- a challenger beats it by **HYS_DWELL_OVERRIDE = 0.25** outright.

Crisis/distress/grief/anger hard-vetoes bypass the gate — safety
outranks stickiness. `select_stack()` pins the gated winner to the
front of the ranking before composition, so the ensemble builds around
the stable lens.

## Blending vs single lens

`blend_weights()` returns a continuous top-3 activation profile
(softmax, weights sum to 1), exposed in `status()["blend"]`.

- **Blending applies to:** status display, composition-engine input,
  and any future response mixing.
- **A single lens is required for:** the orchestration loop's active
  lens (`loop.py` calls `set_active`), an explicit user lock
  (`levi nervous` has no lock flag; the lock comes from
  `--personality`), and crisis hard-vetoes.

Explicit lock always wins over matrix, hysteresis, and blend.

## Persistence & migration

State lives in `~/.levi/nervous_system.json` (affect, affinity usage,
lock, incumbent + dwell counter, last blend/scores). Old files that
only carry the six original dimensions load without crashing; the new
axes migrate sensibly: `fatigue = 1 − energy` (slow envelope of low
capacity) and `bond_strain = max(0, 0.35 − bond)` (thin bond implies
strain), with valence 0.55 / dominance 0.50 neutral defaults.

## Honesty

Every string in this subsystem describes LEVI as local-first
neuro-symbolic Synthetic Intelligence. Nothing here claims biological
feeling, sentience, or consciousness — the module docstring, the CLI
header ("internal load — a control surface, not biological feeling"),
and `status()["note"]` all say so explicitly.

## Counts

17 seeded persona affinities (`AFFINITY_SEED`). The `PersonaLattice`
may register additional lenses at runtime; the matrix seeds unknown ids
with baseline 0.12 and learns usage from there. If the seed count
changes, update this number in the same commit (blueprint §2).
