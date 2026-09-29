---
skill_id: grey_snapshot_restore_drill
name: Snapshot Restore Drill
description: Drill snapshot restores under time pressure to validate recovery procedures.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, snapshots, restore, drill]
version: 1.0.0
team: grey
---
# Snapshot Restore Drill

## Purpose

Restore procedures work on paper until they're timed. This drill restores range
components from snapshots under time pressure — validating the runbook, the tooling, and
the grey team's speed when an exercise depends on it.

## When to use

- Periodically, per the range program.
- Before high-stakes exercises.
- After restore-procedure changes.

## Prerequisites

- Verified snapshots to restore from.
- Isolated drill environment.
- Restore runbook.

## Procedure

1. Declare the drill: the scenario (which components 'failed').
2. Execute the restore runbook under time: start the clock at declaration.
3. Time each stage: snapshot selection, restore execution, verification, handover.
4. Record deviations: runbook steps that didn't work, tooling gaps, slow stages.
5. Verify the restored components fully before stopping the clock.
6. Deliver the drill report with runbook fixes.

## Expected outputs

- Restore drill timeline.
- Runbook deviation list.
- Runbook fixes.

## Pitfalls

- Drilling against the live range — isolated environment.
- Stopping the clock at 'restore initiated' — the clock stops at verified working.
- Skipping the drill because 'we verified the snapshots' — verification isn't speed.

## References

- Disaster-recovery drill literature.

## Exercise role

The restore drill times the truth — how fast the range actually comes back when the
exercise is waiting.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
