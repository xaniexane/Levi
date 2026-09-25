---
skill_id: factory.intake_triage
name: Intake Triage
description: Reads the Factory Genesis intake queue and reports the line's status at a glance.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, intake, status]
version: 1.0.0
---

# Intake Triage

Read-only status report for the Factory Genesis production line.
Advisory only: this skill reads and reports. It never mutates the queue,
never dispatches builders, spends nothing, touches no accounts.

## How to read the line

1. Read `core/levi/factory/genesis/intake/queue.jsonl` — one JSON object per
   line, each with `id`, `kind`, `working_title`, `source`, `rationale`,
   `status`, `created_at`.
2. Count lines per status: `queued`, `spec'd`, `building`, `proving`,
   `registered`, `done`.
3. Find the oldest line whose status is `queued` or `spec'd` — that is the
   next candidate for the builder.
4. Report: counts per status, the oldest waiting spec (id + working title +
   age), and anything sitting in `building` or `proving` (possible stall).

## Status meanings

- `queued` — intake accepted, no spec yet.
- `spec'd` — spec written from the template, laws declared, ready to build.
- `building` — a builder holds it (one builder per build thread).
- `proving` — implementation done, law→guard→prove gates running.
- `registered` — minted and registered; receipt written.
- `done` — closed out and logged.

## Example report

```
Factory line: 2 queued, 1 spec'd, 1 building, 0 proving, 2 registered.
Oldest waiting: genesis-004 (ddd-inbox-watcher), waiting 3d.
Building now: genesis-003 (mystery-box-pricer), builder 🏭.
```

## Laws

- Read-only: never write to the queue, never dispatch, never mutate.
- Statuses come from the file, never invented.
- If the queue file is missing or a line is malformed, say so plainly —
  never fill the gap with guesses.
