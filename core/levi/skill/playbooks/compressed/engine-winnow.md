---
skill_id: compressed.engine-winnow
name: Winnow Pattern
description: Cluster near-duplicate texts into merge groups with a deterministic canonical keeper — duplicates marked, nothing deleted.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, dedup, clustering, nothing-thrown-away]
version: 1.0.0
---
# Winnow Pattern

## Purpose

Turn a pile of near-identical texts — inbox threads, receipt dumps,
harvested notes, repeated alerts — into merge groups with one canonical
keeper each. Winnowing separates; it never burns. Duplicates are
*marked*, never deleted, per the nothing-thrown-away law.

## When to use

Whenever you face "the same thing said N slightly different ways" and
need the canonical set: dedupe before ingest, collapse repeated alerts
before paging the keeper, merge variant records before archive.

## The pattern

1. **Shape the items.** Each item is `{"id": str, "text": str}`. Ids must
   be unique — a duplicate id is refused outright, never merged
   silently.
2. **Pick the threshold.** `threshold` is the `difflib.SequenceMatcher`
   ratio in (0, 1], default 0.85. Exact duplicates match at 1.0.
   Paraphrases land 0.6–0.85. Start at 0.85; drop to 0.75 only when you
   can name what a 0.75 pair looks like in your data.
3. **Run the engine.** `registry.run("winnow", {"items": items,
   "threshold": 0.85})` — or the `compressed.run-winnow` skill. The
   verdict's `groups` list carries `canonical`, `members`, and
   `duplicate_count` per group.
4. **Read the trace before acting.** Every merge names the ratio that
   caused it: `merged 'b' into 'a' group (ratio=0.92 ≥ 0.85)`. If a
   merge surprises you, raise the threshold — the surprise is data, not
   noise.
5. **Keep everything.** Archive the full verdict — groups *and*
   singletons. The chaff stays in the barn; you just know which sheaf
   is the keeper.

## The laws

- **Partition:** every item lands in exactly one group.
- **Determinism:** same items, same threshold → byte-identical verdict.
- **Canonical:** the keeper is the lexicographically smallest id in the
  group — stated, never negotiated.
- **Honest merge:** below-threshold pairs never merge, no matter how
  suggestive.

## Honest limits

- Comparison is textual, not semantic. "The cat sat" and "a feline
  rested" are different strings; winnow will not call them kin.
- Pairwise comparison is O(n²) — lists over `max_items` (default 2000)
  are refused rather than slow-burned. Shard large corpora first.
- Normalization is casefold + whitespace collapse only. Accents,
  punctuation, and unicode tricks are compared as-is; normalize your
  inputs if your data plays those games.
