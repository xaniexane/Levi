# OWNERSHIP — core/levi/phase3/

**Owner: the END team** (beginning/middle/end formation, Chauncey 2026-09-20).

This directory is the end team's build territory. Other teams: do not
edit files here — connect through the written interface contracts
(`~/workspace/levi-unified-build/end-to-middle-contract.md`), never by
editing.

Subpackages and their salvage-catalog candidates:

| Directory | Candidate | Formal spec |
|---|---|---|
| `prover/` | A5 logic-prover primitives | `salvage-prover-formal-spec.md` |
| `cards/` | A6 HyperCard-style memory cards | `salvage-cards-formal-spec.md` |
| `image/` | A7 image persistence | `salvage-image-formal-spec.md` |
| `linda/` | B9 Linda coordination dialect | `salvage-linda-formal-spec.md` |
| `plan9/` | B10 Plan 9 interface discipline | `salvage-plan9-formal-spec.md` |
| `dataflow/` | B11 dataflow firing-rule semantics | `salvage-dataflow-formal-spec.md` |
| `liveq/` | B12 live queries / message ports / copper timing | `salvage-liveq-formal-spec.md` |
| `crafts/` | C9 crafts pedagogy | `salvage-crafts-formal-spec.md` |
| `builder/` | C10 MUD builder ladder + Habitat split | `salvage-builder-formal-spec.md` |
| `sovmail/` | C12 sovereign mail contract | `salvage-sovmail-formal-spec.md` |

All module names are working titles — naming is Chauncey's, never
declared canon by a worker.

Territory the end team does NOT touch: `core/levi/synthesis/*`,
`docs/SYNTHESIS.md`, `tests/test_synthesis*.py` (beginning team), and
the middle team's directories (scan-mind / blackboard / rule-reflex /
dictionary) once they exist.
