---
skill_id: utility.csv_deduplicate
name: CSV Deduplicate
description: Remove duplicate rows from a CSV, keeping the first occurrence, and report what was dropped.
risk: moderate
permissions: []
requires_confirmation: true
tags: [csv, deduplicate, cleaning]
version: 1.0.0
---

# CSV Deduplicate

CSV Deduplicate reads a CSV, drops rows that exactly repeat an earlier row (or repeat on key columns you choose), keeps the first occurrence, and writes the deduplicated file with a count of what was removed.

## When to use

- Cleaning an export that contains repeated rows.
- Preparing a mailing list with no duplicate entries.
- Removing double-logged events before analysis.

## Steps

1. Decide the duplicate rule: whole-row match, or match on specific key columns.
2. Stream the rows, hashing each row's key; keep the first sighting, count the rest as duplicates.
3. Write the kept rows to a new file in original order.
4. Report total rows in, rows out, and duplicates removed.

## Honest limits

- Duplicate means exact match - near-duplicates ('Jon' vs 'Jonathan') need human judgment, not this skill.
- The first occurrence wins; if a later duplicate held better data, that choice is yours to make first.
- Verify the counts before deleting the original.

Original work authored for LEVI - utilities pack.
