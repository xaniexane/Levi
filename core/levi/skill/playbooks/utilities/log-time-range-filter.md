---
skill_id: utility.log_time_range_filter
name: Log Time Range Filter
description: Keep only the log lines whose timestamps fall inside a window you give.
risk: moderate
permissions: []
requires_confirmation: true
tags: [logs, filter, timestamps]
version: 1.0.0
---

# Log Time Range Filter

Log Time Range Filter parses timestamps at the start of each log line, keeps the lines inside your [start, end] window, and writes them to a new file. Lines without a parseable timestamp are skipped and counted.

## When to use

- Isolating what happened during an incident window.
- Trimming a day-long log to the hour that matters.
- Preparing a time-boxed excerpt for someone else.

## Steps

1. Confirm the log's timestamp format and give the window in the same format (assume UTC unless the log says otherwise).
2. Stream the log, parse each line's timestamp, keep lines inside the window.
3. Write kept lines to a new file; report kept, skipped (unparseable), and total.
4. Spot-check the first and last kept lines against your window bounds.

## Honest limits

- Needs a consistent timestamp format - mixed formats need normalizing first.
- Timezone-naive timestamps are treated as UTC and labeled as such.
- Skipped lines are counted and reported, never silently dropped.

Original work authored for LEVI - utilities pack.
