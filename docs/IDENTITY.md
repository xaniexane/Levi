# IDENTITY — the variant engine

`levi identity reflect|variants|compost|compress|cycle|genome`
(`python -m levi.identity` for the same surface.)

The identity variant engine is the reflect → reconstruct → variant →
compost → compress → genome loop, built from Chauncey's own architecture:

- **Echo** (`identity/echo.py`) holds the mirror. `EchoEngine.reflect(identity)`
  returns a `Reflection`: a faithful copy of the identity, a coherence score
  (0–1), and detected fractures (out-of-range traits, invalid params,
  duplicate/conflicting fragments). It repairs nothing.
- **Mandella** (`identity/mandella.py`) is the surgeon. Given a Reflection it
  repairs the fractures, then produces **variants** — controlled mutations:
  parameter drift (±15%), trait swaps, trait drift (±0.10), fragment
  recombination. Deterministic under an explicit seed. This is an evolution
  engine, not just repair: reflect → reconstruct → variant → reflect again.
- **REIM** (`identity/reim.py`) composts outcomes. `compost(outcome)` breaks a
  run's result into lessons: failure signature (sha256), classified cause,
  one-line lesson, severity. Information is never destroyed — each lesson
  keeps the signature and the raw notes excerpt.
- **RIEM** (`identity/riem.py`) is **controlled compression** — not collapse.
  `compress(lessons, genome)` aggregates lessons by cause, promotes them when
  corroboration ≥ 2 or severity is high, and emits genome deltas: bounded
  trait adjustments, new guard rules, and the promoted entries. Every
  promoted entry retains its failure signature + cause, so the genome stays
  auditable back to the lesson. Like zipping, not burning: signal kept,
  noise dropped.
- **Genome** (`identity/genome.py`) is the heritable trait store:
  `~/.levi/identity/genome.json` (dir 0700, file 0600). New identities
  inherit the genome's trait mix via `inherit_traits()`.
- **Cycle** (`identity/cycle.py`) runs the full loop for one identity, with
  a pluggable scoring function (default: Echo coherence of each variant).
  The winner's outcome is composted, compressed, and applied to the genome.

## Whole-organism scope

`levi identity reflect --scope all` reflects **every module declared in the
interop manifest** — LEVI looking at its own insides. Each module's identity
is its declaration (provides/ requires / CLI surface) plus wiring traits;
Echo scores coherence and flags fractures such as missing dependencies or
empty provides lists.

`levi identity cycle --scope all` runs reflect → reconstruct → variants for
every module, with **interpenetration**: a variant may inherit traits from
another module (controlled cross-pollination), with provenance recorded
(`provenance.inherited_traits`: which trait came from which module).
Risk ceiling: variants are stored as **candidates for review** in the genome
store (`genome --module <name>`); module code is never touched.

## Examples

```bash
# reflect one identity from JSON
echo '{"name":"scout","traits":{"caution":0.7},"params":{},"fragments":[]}' \
  | levi identity reflect

# produce 5 seeded variants
levi identity variants --n 5 --seed demo < identity.json

# full cycle (updates ~/.levi/identity/genome.json)
levi identity cycle --seed demo --notes "evening run" < identity.json

# reflect the whole organism
levi identity reflect --scope all | head -40

# cycle every module with cross-pollination, review candidates
levi identity cycle --scope all --seed demo
levi identity genome --module finance
```

## Honest limits

- Coherence is a heuristic (range checks, duplicates, conflicts, dependency
  wiring) — not a learned model of "good identity".
- The default scorer is Echo coherence; plug in a domain scorer for real
  selection pressure, otherwise the loop optimizes tidiness.
- Compression drops raw notes from the genome (they live in the lesson
  records); the retained signal is signature + cause + lesson.
- Genome is local JSON, single-writer assumed; concurrent cycles can
  interleave writes (last write wins on the file, traits are re-read each
  apply).
- This package is the **identity-layer variant engine**; the kernel
  decision-support organs live in `levi/organs/` (branch exploration, stake
  selection, failure composting, genome proposals) and are a separate,
  complementary surface.
