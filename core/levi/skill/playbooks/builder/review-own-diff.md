---
skill_id: builder.review_own_diff
name: Review Your Own Diff
description: Read every line of your diff before it lands; the author is the cheapest reviewer.
risk: info
permissions: []
requires_confirmation: false
tags: [review, quality, honesty]
version: 1.0.0
---

# Review Your Own Diff

The person who wrote the change is the cheapest reviewer it will ever
get. Read the diff line by line before it lands — not the code, the
*diff*: only what changed, which is the only part that can surprise
anyone.

## The practice

1. **Read it cold.** Step away, come back, read the diff as if a
   stranger wrote it. Strangers catch what familiarity excuses.
2. **Interrogate every line.** For each hunk: why is this here, what
   does it touch, what breaks if it is wrong? A line you cannot
   justify is a line you should not land.
3. **Hunt the drive-bys.** Fixes to files you did not mean to touch,
   reformats of code you did not mean to change, new files you did
   not mean to add — drive-bys are how shared trees rot.
4. **Run what you claim.** If the commit says tests pass, the command
   ran in this session on this diff. Claims without runs are wishes.

## The tell

If you catch yourself skimming — eyes moving, brain approving — stop
and read that hunk aloud. Skimming is how your own typo ships.

## What this is not

Self-review is not self-approval. You are not asking "am I good";
you are asking "is this exactly what I meant, and nothing else."
