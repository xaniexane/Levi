# Receipt — OPERATORS recipe run 2026-09-29 (glyph 🎛️)

## Counts
- operator playbooks live: 18 → 7 (day, loop, create, decide, commit, no, xyz)
- absorbed originals stored: 16 (this dir, byte-identical)
- total accounted: 23 (18 originals incl. 2 kept + 5 new composites)
- operator-texts skill surface: 1 → 1 (57 lines, 0 cuts — verified dense)

## π-lottery selections (deterministic; script /tmp/recipe-operators-lottery.py, run twice byte-identical)
- pi_digits_used: 141592653589793
- a_polish_order: voice-then-title (first pi digit=1, odd) → create.md phases ③voice ④title
- b_merge_slug: commit (sum of first 3 pi digits=6 mod 3, candidates [commit, lock, pledge])
- c_display_order: commit > day > no > create > decide > xyz > loop
- d_chain_map_order (permutation lottery, pi-seeded Fisher-Yates over 10 cross-linked pairs):
  review->streak, spark->cut, ship->review, eighty->triage, cut->title,
  cut->voice, actions->lock, triage->mvd, blocker->gavel, mvd->deep

## Proofs
- Determinism: lottery script two runs → diff empty (PASS)
- Byte reconciliation: 16 stored originals sha256 == pre-move hashes; no.md + xyz.md
  unchanged in place (PASS); hashes in hashes-before.txt
- Caps (exponential-growth guard): ≤5 composites (5), ≤4 phases each (4),
  ≤60 lines each (53/53/54/59/57), exactly 1 merge (commit), 0 new standalone
- RIEM recursion: second curation pass over composites — 0 cross-file duplicate
  sentences, all under cap, nothing left to cut
- Tests: tests/test_operator_skills.py 8/8 green from zero
- Linter: ruff clean on changed Python files; py_compile OK
- Inverse echo: every composite carries a `Source echo ⇐` footer; full map in PROVENANCE.md
