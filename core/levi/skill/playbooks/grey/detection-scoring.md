---
skill_id: grey_detection_scoring
name: Detection Scoring
description: Score blue-team detections against the exercise's detection objectives.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, scoring, detection, blue-team]
version: 1.0.0
team: grey
---
# Detection Scoring

## Purpose

Detection is usually the highest-weighted exercise objective. This scoring evaluates
each expected detection: was it caught, how fast, with what fidelity — against the
evidence, not against claims.

## When to use

- After exercise execution, during evaluation.
- Per detection objective in the scoring model.

## Prerequisites

- Scoring model with detection elements.
- Evidence package with detection artifacts.
- Red-team ground truth (what actually happened, when).

## Procedure

1. For each red action, compare against blue-team detections: detected, missed, or false-
   positive.
2. Score detection latency: action time (red ground truth) to alert time (blue evidence).
3. Score fidelity: did the alert identify the right technique, host, and scope?
4. Penalize fairly: missed detections per the rubric, false positives per the noise
   standard.
5. Reconcile with the red team: confirm the ground truth before finalizing misses.
6. Publish detection scores with the evidence cited.

## Expected outputs

- Detection scorecard per objective.
- Latency measurements.
- Reconciled ground truth.

## Pitfalls

- Scoring detections without red-team ground truth — reconcile first.
- Latency measured against unsynchronized clocks — the NTP setup matters here.
- False-positive penalties without a noise standard — define it in the model.

## References

- Detection-engineering literature (public).

## Exercise role

Detection scoring is where the exercise's honesty lives — ground truth from red,
evidence from blue, scored against the published rubric.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
