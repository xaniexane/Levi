---
skill_id: factory.watch_summary
name: Watch Summary
description: Summarizes the DemandPulse watchlist in plain speech; statuses only, never invented traction.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, demandpulse, watchlist, summary]
version: "1.0.0"
---

# Watch Summary

Summarizes the DemandPulse watchlist in plain speech. Statuses only —
the summary reports what the watchlist says, never invented traction.

## How to read the watchlist

- Source: `~/.levi/demand/watchlist.json` (if present).
- Count items per status; name the longest-parked item from the file.

## Laws

1. Never invent an item's status — report what the file says.
2. Absent watchlist file means zero items, said plainly.
3. No traction claims, no revenue claims, no completion claims.
4. The summary is advisory; decisions stay with Chauncey.

## Limits

- Never posts, publishes, replies, or writes anywhere.
- Never mutates the watchlist; never reorders priorities.

## Notes

- Pairs with the Watch Tender agent (watchtender): the agent watches,
  this skill summarizes for a human reading.
