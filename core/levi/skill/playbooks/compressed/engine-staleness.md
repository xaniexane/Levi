---
skill_id: compressed.engine-staleness
name: Staleness Pattern
description: Score freshness on any list of timestamped items — fresh, stale, or expired — mark the old, delete nothing, with the exact age and boundary beside every verdict.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, freshness, decay, audit, mark-never-delete]
version: 1.0.0
---
# Staleness Pattern

## Purpose

Turn "is this still true?" into a machine-scored receipt. You hand the
engine a list of timestamped items and a named policy — `short`, `day`,
`week`, or `long` — and it scores each item's freshness: **fresh**
(still inside the window), **stale** (past fresh — re-check before
trusting), **expired** (past the point of trust). Classification is
marking, never pruning: expired items stay in the verdict, labeled, so
rot never hides by deletion.

## When to use

- Before trusting an old report, receipt, or scan: score the table and
  re-check everything past `stale`.
- In audits and growth cycles: attach a staleness verdict to any table
  you hand upward, so the reader knows what aged out.
- On build queues and backlogs: `short` for hot signals, `day` for
  daily drafts, `week` for weekly summaries, `long` for canon material.

## Inputs

- `items`: list of `{id, seen_at}` — `seen_at` is an ISO-8601 stamp.
  Items without a real stamp are refused, never scored.
- `policy`: one of `short` (1h/24h), `day` (24h/7d), `week` (7d/30d),
  `long` (30d/180d) — or a custom `{fresh_sec, stale_sec}` pair.
- `now`: optional ISO-8601 stamp for deterministic replays; defaults to
  the current UTC time.

## Reading the verdict

Every item carries `state`, `age_sec`, a 0–1 `score` (1.0 at birth, 0.0
at the stale boundary), plus the `fresh_sec`/`stale_sec` boundaries and
the policy that set them — the evidence, not a bare label. `counts`
summarizes fresh/stale/expired; `confidence` is the mean score.

## Laws

1. No stamp, no score — unstamped and future-stamped items are refused.
2. Same inputs, byte-identical verdict (sans `ran_at`).
3. Expired is a label, not a deletion — every input item appears in the
   output, or the run is a bug.
