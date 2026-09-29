---
skill_id: grey_red_team_effectiveness_scoring
name: Red Team Effectiveness Scoring
description: Score red-team effectiveness: objective achievement and tradecraft quality.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, scoring, red-team, effectiveness]
version: 1.0.0
team: grey
---
# Red Team Effectiveness Scoring

## Purpose

The red team gets scored too: did they achieve their objectives, with what tradecraft,
and what did their path reveal about the defenses? This scoring keeps red honest and
extracts the defensive lessons.

## When to use

- After exercise execution.
- For red-team capability assessment.

## Prerequisites

- Red-team objectives from the scenario.
- Red-team activity logs (their own reporting).
- Blue-team detection results for comparison.

## Procedure

1. Score objective achievement: which red objectives were met, with evidence.
2. Score tradecraft: stealth (detections per action), efficiency, and ROE compliance.
3. Score the path: which defensive layers did each attack path defeat, and where did it
   stop?
4. Evaluate ROE compliance: any boundary crossings are scoring penalties and incident
   reports.
5. Compare red claims against blue-team evidence and grey-team observations; reconcile.
6. Publish red scores with the defensive lessons each path produced.

## Expected outputs

- Red-team scorecard per objective.
- Tradecraft assessment.
- Defensive-layer defeat map.
- ROE-compliance record.

## Pitfalls

- Scoring red on stealth alone — objective achievement and lessons matter more.
- Unreconciled red claims — verify against blue evidence.
- ROE violations scored quietly — they're incidents, reported as such.

## References

- Red-team operations literature (public).

## Exercise role

Red-team scoring serves the defense — every red point is a defensive lesson documented.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
