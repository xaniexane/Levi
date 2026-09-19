# Academy Differentiators — Novel Measures No One Is Using

Six instruments that make the boot camp unreplicable. Each is stdlib-only,
hermetic (no network), and owner-scoped under `<LEVI_HOME>/academy/`.

## 1. Sealed skill receipts (`differentiators/receipts.py`)

Every completed module mints a tamper-evident skill receipt — a Veil-lineage
sealed envelope binding learner, module, score, and rubric checks. Anyone can
verify; no one can alter. Verification fails loudly on tampered envelopes or
payloads.

- `mint_receipt(learner_id, module_id, score, checks)` → receipt + envelope
- `verify_receipt(envelope)` → payload or raises `SealError`

## 2. Failure compost (`differentiators/compost.py`)

A failed rubric check is not a grade — it is raw material. `compost_failure`
turns exactly what was missed into a targeted remediation drill: one task per
failed check, assigned immediately, with a stale-point cap so old failures
don't rot. REIM lineage: failure becomes material, not shame.

## 3. Stake-under-fog drills (`differentiators/stakes.py`)

Learners stake reputation points on answers *before* the reveal. Correct stakes
pay 1:1; wrong stakes burn. The instrument tracks implicit confidence and
Brier calibration, not correctness alone — `calibration_report` grades how
well a learner's stakes match their outcomes. The shared `brier_score` helper
is also the math behind metacognition scoring (`academy/science.py`).

## 4. Corroboration-gated mastery (`differentiators/mastery.py`)

A skill requires successful demonstrations across **three distinct contexts**.
Repeating one context three times does not count — independent corroboration
does. `record_demonstration` tracks contexts; `is_mastered` and `mastery_status`
report the gate.

## 5. Skill decay (`differentiators/decay.py`)

Skills have a 30-day half-life: `strength = 0.5^(days/30)`. Below 0.5 a skill
is *due* — flagged for retesting, not silently trusted. A failed retest zeroes
the skill and flags remediation. The spaced-repetition scheduler
(`academy/methods.py`) layers on this model: reviews land just before the
strength would cross threshold.

## 6. Live-fire finals (`differentiators/livefire.py`)

The final is supervised real work through the existing nursery workload
router — a registered, verified template (sort/filter/transform), never
multiple choice. A verified pass mints a sealed receipt; a refusal or
verification failure is recorded and composted.

## Sealing

`differentiators/_seal.py` is the Academy-scoped Veil-lineage seal:
Encrypt-then-MAC with a keeper-held key, owner-only state. Honest limit: the
construction is a documented stdlib HMAC construction, not AES-GCM.

## Tests

`tests/test_academy_differentiators.py` — 17 tests, all green, home-scoped
(via `LEVI_HOME`), deterministic, no network.
