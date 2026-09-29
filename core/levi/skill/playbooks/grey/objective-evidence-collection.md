---
skill_id: grey_objective_evidence_collection
name: Objective Evidence Collection
description: Collect scoring evidence during the exercise: logs, timelines, and artifacts.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, scoring, evidence, collection]
version: 1.0.0
team: grey
---
# Objective Evidence Collection

## Purpose

Scores need evidence: the log line that proves detection, the timestamp that proves
response time. This collection runs during the exercise, capturing the evidence the
scoring model demands — before logs roll and memories fade.

## When to use

- During exercise execution.
- Continuously, not after the fact.

## Prerequisites

- Scoring model with evidence standards.
- Logging pipeline verified.
- Evidence-collection tooling/access.

## Procedure

1. Monitor the exercise against the scoring elements; capture evidence as events occur.
2. Timestamp everything against the synchronized range clock.
3. Collect artifacts: alert screenshots, ticket records, timeline entries, team
   communications.
4. Maintain the evidence log: element, evidence, timestamp, collector.
5. Protect evidence integrity: write-once storage, hashes for key artifacts.
6. Hand the evidence package to the scorers at exercise end.

## Expected outputs

- Evidence package per scoring element.
- Evidence log with timestamps.
- Integrity verification (hashes).

## Pitfalls

- Post-exercise evidence hunting — collect during, not after.
- Undated evidence — timestamps against the range clock or it's not evidence.
- No integrity protection — hash the key artifacts.

## References

- Digital-evidence handling literature.

## Exercise role

Evidence is perishable — collected during the exercise with timestamps, or it's
reconstruction, not evidence.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
