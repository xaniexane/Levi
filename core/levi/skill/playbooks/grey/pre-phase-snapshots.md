---
skill_id: grey_pre_phase_snapshots
name: Pre-Phase Snapshot Capture
description: Capture snapshots before each exercise phase for phase-level rollback.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, snapshots, phases, rollback]
version: 1.0.0
team: grey
---
# Pre-Phase Snapshot Capture

## Purpose

Phases go wrong: a phase's destruction breaks the next phase's setup. Pre-phase
snapshots give the grey team phase-level rollback — restore the phase boundary without
losing the whole exercise.

## When to use

- Before each exercise phase.
- Before destructive phases especially.

## Prerequisites

- Snapshot strategy with phase points defined.
- Phase boundary identified (exercise paused or quiesced).

## Procedure

1. At the phase boundary, quiesce exercise traffic.
2. Capture the phase snapshots per the component list — fast, automated, timestamped.
3. Verify capture completion per component (don't assume the job finished).
4. Record the phase-snapshot manifest with the exercise timeline position.
5. Resume the exercise; keep the snapshots until the phase's analysis is done.
6. Delete per the retention policy after the analysis window.

## Expected outputs

- Phase-snapshot manifest.
- Capture-verification per component.
- Retention/deletion log.

## Pitfalls

- Snapshotting a live firefight — quiesce first or capture garbage.
- Assuming the snapshot job finished — verify per component.
- Deleting before analysis — retention follows the analysis window.

## References

- Range-operations literature.

## Exercise role

Pre-phase snapshots are the exercise's save points — quick, verified, and the reason a
bad phase doesn't end the exercise.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
