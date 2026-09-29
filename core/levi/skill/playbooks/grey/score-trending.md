---
skill_id: grey_score_trending
name: Exercise Score Trending
description: Trend exercise scores across iterations to measure program improvement.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, scoring, trending, metrics]
version: 1.0.0
team: grey
---
# Exercise Score Trending

## Purpose

One exercise is a snapshot; a program is a trend. This trending compares scores across
exercise iterations — detection rates over time, response-time curves — to prove the
security program is improving (or to show where it isn't).

## When to use

- Across exercise iterations in a program.
- For security-program metrics reporting.

## Prerequisites

- Comparable scoring models across iterations (normalize where models changed).
- Archived scores and evidence summaries.

## Procedure

1. Normalize scores across iterations for model changes; document the normalization.
2. Trend the key metrics: detection rate, mean time to detect/respond, objective
   achievement.
3. Correlate trends with program changes: new tooling, training, headcount.
4. Identify plateaus and regressions; investigate the causes.
5. Report the trend to leadership with the story behind the numbers.
6. Feed the findings into the next exercise's objectives.

## Expected outputs

- Trend report with normalized metrics.
- Correlation analysis with program changes.
- Next-exercise objective recommendations.

## Pitfalls

- Trending across incomparable models without normalization — document the adjustments.
- Cherry-picked metrics — trend the full scorecard.
- Trends without the story — numbers need the program context.

## References

- Security-metrics literature.

## Exercise role

Trending turns exercises into a program — the proof that the work compounds instead of
repeating.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
