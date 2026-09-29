---
skill_id: grey_exercise_artifact_repository
name: Exercise Artifact Repository Setup
description: Set up the artifact repository for exercise plans, findings, and reports.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, setup, artifacts, repository]
version: 1.0.0
team: grey
---
# Exercise Artifact Repository Setup

## Purpose

Exercises generate plans, rules of engagement, findings, timelines, and reports — all of
which need versioning, access control, and retention. This setup creates the exercise's
document home before the exercise starts.

## When to use

- At exercise kickoff, before planning artifacts accumulate.
- For exercise programs needing cross-exercise trending.

## Prerequisites

- Exercise codename and classification level.
- Participant roster with roles (for access control).

## Procedure

1. Create the exercise workspace: plans, ROE, findings, timelines, reports sections.
2. Apply access control per role: red sees red, blue sees blue, grey sees all, observers
   see the white-card view.
3. Set up finding templates and severity scales for consistent reporting.
4. Configure retention and archival policy for exercise artifacts.
5. Brief participants on where things live and the naming conventions.

## Expected outputs

- Exercise workspace with access control.
- Finding/report templates.
- Retention policy.

## Pitfalls

- Findings in chat threads instead of the repository — centralize from day one.
- Wrong access control leaking red plans to blue (or vice versa) — verify permissions.
- No retention policy — exercise data lingering indefinitely.

## References

- Exercise-management literature.

## Exercise role

The repository is the exercise's institutional memory — set up before the first finding,
or findings live in chat history.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
