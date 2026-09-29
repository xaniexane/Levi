# Provenance — operator playbooks absorbed 2026-09-29

## What
16 operator playbook originals, moved byte-identical out of the live core set
(`core/levi/skill/playbooks/operator/`) on 2026-09-29 by the OPERATORS-domain
recipe worker (glyph 🎛️, Chauncey's signature-recipe run). NOTHING DELETED —
every byte below is preserved here and regenerable on demand.

## Why
Chauncey's order: "those are the recipes — run it on all skills knowledge
operators internals engines daemons etc." Applied to the operator domain:
CURATE (dedupe/merge overlapping capabilities) → INTERPENETRATION (chain into
composite operator skills) → CONTROLLED COMPRESSION (absorbed components leave
the live core set; stored here with provenance, never deleted).

## Absorbed originals → absorbing composites (inverse echo map)
| Original (this dir) | Absorbed into (live) | Role in the composite |
|---|---|---|
| eighty.md | operator.day | ① vital few |
| triage.md | operator.day | ② triage buckets |
| mvd.md | operator.day | ③ the day's three |
| deep.md | operator.day | ④ deep-work block |
| ship.md | operator.loop | ① define done + ship |
| review.md | operator.loop | ② close the day |
| streak.md | operator.loop | ③ keep the streak |
| spark.md | operator.create | ① generate |
| cut.md | operator.create | ② cut |
| voice.md | operator.create | ③ voice (π-lottery order: voice→title) |
| title.md | operator.create | ④ title |
| blocker.md | operator.decide | ① classify the blocker |
| stress.md | operator.decide | ② stress-test the plan |
| gavel.md | operator.decide | ③ gavel ruling |
| actions.md | operator.commit | merged: extract actions, one owner + one deadline |
| lock.md | operator.commit | merged: commitment + check-in watch |

Kept live (not absorbed, standalone): no.md (operator.no), xyz.md (operator.xyz).

## How to regenerate / restore
- Composites are self-contained: each carries its absorbed phases as full
  steps plus a `Source echo ⇐` footer naming its sources.
- Full restore of the pre-recipe live set:
  `cp stored/2026-09-29-operator-playbooks/*.md core/levi/skill/playbooks/operator/`
  (then remove the 5 composites if a pure restore is wanted).
- Deterministic selections (π-lottery): see the recipe receipt in the worker's
  final report — lottery script `/tmp/recipe-operators-lottery.py`
  (π digits 141592653589793…): polish order voice→title (digit 1, odd);
  merge slug "commit" (Σ first 3 digits = 6 mod 3); INDEX display order
  commit > day > no > create > decide > xyz > loop.

## Integrity
Pre-move sha256 of all 18 originals: /tmp/recipe-operators-hashes-before.txt
(worker run). Post-move verification: 16 stored files match; no.md + xyz.md
unchanged in place; 5 composites are new files (day, loop, create, decide,
commit). Live count 18 → 7; stored 16; total accounted 23.
