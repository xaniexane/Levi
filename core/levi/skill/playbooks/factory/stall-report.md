---
skill_id: factory.stall_report
name: Stall Report
description: Expanded factory line report with stall ages; read-only, reports only.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, report, stalls, status]
version: "1.0.0"
---

# Stall Report

Expands the factory line report with stall ages: for each queued or
parked item, how long it has waited since intake. Read-only.

## How to report

- Read the intake queue (`core/levi/factory/genesis/intake/queue.jsonl`).
- For each item not registered, compute the age from `created_at` to now.
- Longest-waiting items first; parked items flagged separately.

## Laws

1. Ages are computed from the queue's own timestamps, never guessed.
2. Never reorders or reprioritizes the queue — the report shows, Chauncey decides.
3. Stalled is a description, never an accusation.
4. Report the method so the ages are repeatable.

## Limits

- Never mutates the queue; never marks items done.
- Never routes around a stall on its own — routing is his word or the
  stall-routing rule through his line.
- Never invents reasons for a stall.

## Notes

- Extends the line report (factory.line_report); the stall ages are the
  addition.
