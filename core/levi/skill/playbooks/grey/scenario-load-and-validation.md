---
skill_id: grey_scenario_load_and_validation
name: Scenario Load and Validation
description: Load the exercise scenario and validate it end-to-end before execution.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, setup, scenario, validation]
version: 1.0.0
team: grey
---
# Scenario Load and Validation

## Purpose

The scenario — attack paths, injects, objectives — must work before the exercise starts.
This validation walks the scenario end-to-end in the range: every attack path
executable, every inject deliverable, every detection reachable — fixing the stage
before the audience arrives.

## When to use

- After range provisioning, before exercise execution.
- When the scenario changes (re-validate).

## Prerequisites

- Scenario document with attack paths and injects.
- Provisioned range with logging verified.

## Procedure

1. Walk each red attack path in the range: verify the vulnerabilities exist, the paths
   execute, the canary objectives are reachable.
2. Validate each inject: deliverability, timing, and the expected team response surface.
3. Verify the blue team's detection opportunities: does the telemetry for each path
   actually flow?
4. Check the timing: does the scenario fit the exercise window?
5. Fix or cut what doesn't work; document deviations from the scenario document.
6. Sign off scenario-readiness with the exercise director.

## Expected outputs

- Scenario-validation report with deviations.
- Timing analysis.
- Readiness sign-off.

## Pitfalls

- Unvalidated scenarios — the exercise discovers the broken path live.
- Skipping the blue-team detection check — a path with no telemetry is a wasted path.
- No timing check — scenarios that don't fit the window.

## References

- Exercise-design literature.

## Exercise role

Scenario validation is the dress rehearsal — every path walked, every inject tested,
before the clock starts.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
