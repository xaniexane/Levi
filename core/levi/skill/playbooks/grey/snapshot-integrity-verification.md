---
skill_id: grey_snapshot_integrity_verification
name: Snapshot Integrity Verification
description: Verify snapshot integrity and restorability on a schedule.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, snapshots, integrity, verification]
version: 1.0.0
team: grey
---
# Snapshot Integrity Verification

## Purpose

Snapshots rot: storage corrupts, formats age, dependencies break. This verification
proves — on a schedule, not on hope — that the snapshots the range depends on actually
restore.

## When to use

- On the strategy's verification schedule.
- Before any planned reset that depends on the snapshots.
- After storage changes.

## Prerequisites

- Snapshot manifest with locations.
- Isolated verification environment (never verify by restoring over the live range).

## Procedure

1. Select snapshots per the verification schedule (rotate coverage so everything gets
   tested).
2. Integrity-check: hashes, format validity, dependency completeness.
3. Test-restore into the isolated environment; verify the restored component boots and
   functions.
4. Record results per snapshot: verified, degraded, or failed.
5. For failures: re-capture from the live range (if the live state is good) or escalate.
6. Report verification status to the exercise director.

## Expected outputs

- Verification report per snapshot.
- Failure/remediation log.
- Coverage rotation record.

## Pitfalls

- Verifying by restoring over production — isolated environment, always.
- Hash-checks without test restores — integrity isn't restorability.
- 100% verification every time — rotate coverage, it's sustainable.

## References

- Backup verification literature.

## Exercise role

Snapshot verification is the range's honesty check — proven by restore, on a schedule,
before they're needed.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
