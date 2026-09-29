---
skill_id: grey_fairness_monitoring
name: Exercise Fairness Monitoring
description: Monitor exercise fairness: information asymmetry, scenario balance, and team welfare.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, referees, fairness, monitoring]
version: 1.0.0
team: grey
---
# Exercise Fairness Monitoring

## Purpose

Exercises must be fair to be useful: teams need the information the scenario promises,
the scenario must be winnable, and nobody should be set up to fail. This monitoring
watches fairness continuously and corrects drift.

## When to use

- Throughout exercise execution.
- Especially in competitive and assessment exercises.

## Prerequisites

- Fairness criteria from the scenario design.
- Monitoring feeds (team status, scenario progress).

## Procedure

1. Monitor information flows: is each team getting what the scenario promised, nothing more
   or less?
2. Track scenario balance: are objectives achievable, or has the scenario drifted
   unwinnable?
3. Watch for unintended advantages: tooling gaps, access mistakes, leaked information.
4. Correct drift in real time: re-balance injects, fix access, re-brief as needed — logged
   as referee actions.
5. Monitor team welfare: fatigue, frustration, safety — fairness includes people.
6. Report fairness status in the after-action.

## Expected outputs

- Fairness-monitoring log.
- Corrective actions with rationale.
- After-action fairness assessment.

## Pitfalls

- Fairness as an afterthought — monitor from the start.
- Correcting without logging — every intervention is a referee action, recorded.
- Confusing fairness with easiness — fair means winnable and honest, not easy.

## References

- Exercise-design literature.

## Exercise role

Fairness is what makes exercise results meaningful — monitored continuously, corrected
openly, reported honestly.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
