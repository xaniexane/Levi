# levi.si — Builder/Hicomb intelligence layer

Local-first intelligence both the Builder pipeline and Hicomb call:
**analyze / decide / generate**, backed by the rules engine first and
his own brain weights second. Big-provider models are teachers only
(offline training signal) — never runtime seats. He is the provider,
not the renter.

This package coexists with the assembled SI turn (`levi.si.turn`):
the turn is the deliberating mind; this layer is the consult interface
his builder tools call. New files only — no Builder, Hicomb,
buzztunes, or brain core file was modified (L6).

## The tiers (in order)

1. **rules** — deterministic, always available. Plan briefs, review
   checklists, focus params, rankings. Honest about being rules.
2. **brain** — his own `tiny-gpt` weights, explicit-only, lazy-loaded.
   Raw continuation, labeled **not reasoning** everywhere it appears,
   confidence 0.25, never a contract payload (L1, L5).
3. **operator brains** — the upgrade lane. When the operator-training
   thread lands trained brains, they slot in as a third tier behind
   the same `SIEngine` interface. Not wired yet; the interface is ready.

## Use

```python
from levi.si.engine import SIEngine

si = SIEngine()
brief = si.consult("plan-brief", {"description": "a notes app"})
# brief.tier == "rules"; brief.data has entities/modules/api/ambiguities
spark = si.consult("idea-spark", {"prompt": "offline sync"})
# tier "brain" when the weights load, else rules fallback — always labeled
notes = si.consult("review-notes", {"description": "..."})
pick  = si.consult("focus-pick", {"minutes": 25, "mood": "calm"})
rank  = si.decide(options, {"speed": 0.6, "cost": 0.4})
```

`consult()` never raises on backend failure — it degrades to rules and
says so (L3). Unknown kinds raise `ValueError` (programmer error).

## Builder wiring (`builder_gen.py`)

- `si_planner_generator(prompt, system)` — a real `Generator` for the
  Builder's planner stage. Emits schema-valid spec JSON with
  `spec_source="si-rules"`; raises `GenerationError` if it cannot, so
  the pipeline's honest heuristic fallback runs instead of a corrupt
  spec (L5).
- `si_generator(prompt, system)` — full-pipeline generator: SI plans,
  other stages honestly decline (their scaffold fallbacks run).
  `run_build(..., generate=si_generator)` completes fully offline.
- `si_refine_notes(plan_summary)` — rules-tier refinement notes for
  the `levi.builders` plan/refine steps to consult.

The Builder's planner seat is his builder/developer twin's seat; this
module is the intelligence that seat consults. Nothing more is built on
that framing — his words stay the spec.

## Hicomb wiring (`hicomb_backend.py`)

`BrainBackend` structurally implements `levi.hicomb.ai.ModelBackend`:

```python
from levi.si.hicomb_backend import BrainBackend
from levi.hicomb.ai import PairProgrammer
prog = PairProgrammer(backend=BrainBackend())
```

Completions come back `source="model"`,
label `"model · brain-draft (not reasoning)"`, confidence 0.25. Brain
unavailable → `available()` is False → PairProgrammer reports
local-only, exactly as before. No Hicomb core rewrite.

## Music (`plugins/`)

focus-flow: buzztunes-backed focus audio with real playback —
`FocusSession.plan` (SI params + buzztunes queue) and
`FocusSession.render` (real playable WAV, synthesized ambience).
The Hicomb cell drives in-editor pad control. See
`plugins/README.md` for the open "and more" lane.

## Honest limits (L4)

- The tiny brain (3.27M params) produces garbled continuation on code
  prompts (measured 2026-09-25). It is a spark, not a planner.
- The focus pad is synthesized ambience, not music; the buzztunes
  queue is curated order, not audio.
- Provider models never run here — not now, not as fallback.

## Laws and proof

`laws.py` declares L1–L6 and maps each to tests. The proof is
`tests/test_si_layer.py`: invariant/property checks, honestly
described as tests, not formal proof (his law-guard-prove rule).
