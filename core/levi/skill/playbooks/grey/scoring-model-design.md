---
skill_id: grey_scoring_model_design
name: Exercise Scoring Model Design
description: Design the exercise scoring model: objectives, weights, and evidence standards.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, scoring, design, exercise]
version: 1.0.0
team: grey
---
# Exercise Scoring Model Design

## Purpose

Scoring turns exercise activity into assessment: which objectives were met, how well,
with what evidence. This design produces the scoring model before execution —
objectives, weights, evidence standards — so scoring is measurement, not opinion.

## When to use

- During exercise planning, before execution.
- For competitive exercises especially.
- When trending scores across exercise iterations.

## Prerequisites

- Exercise objectives from the scenario.
- Stakeholder agreement on what 'good' looks like.

## Procedure

1. Decompose objectives into scorable elements: detection, response time, containment,
   reporting.
2. Assign weights reflecting exercise priorities; document the rationale.
3. Define evidence standards per element: what proof earns the points (log excerpts,
   timelines, artifacts).
4. Design the scoring rubric: full/partial/no-credit criteria with examples.
5. Build the score sheet (tooling or template) and test it against a walkthrough.
6. Publish the model to all teams before execution — no secret scoring.

## Expected outputs

- Scoring model with weights and rationale.
- Evidence standards per element.
- Tested score sheet.

## Pitfalls

- Secret scoring models — publish before execution.
- Weights without rationale — document why detection outweighs speed (or vice versa).
- No evidence standards — scoring becomes opinion.

## References

- Exercise-evaluation literature; CTF scoring models (public).

## Exercise role

The scoring model is the exercise's grading rubric — designed and published before
anyone is graded.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
