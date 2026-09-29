---
skill_id: grey_pristine_baseline_capture
name: Pristine Baseline Snapshot Capture
description: Capture the pristine baseline snapshot of the full range before exercise traffic.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, snapshots, baseline, capture]
version: 1.0.0
team: grey
---
# Pristine Baseline Snapshot Capture

## Purpose

The pristine baseline is the ground truth every reset returns to. This capture snapshots
the full range — every component, in order — after provisioning and validation, before
any exercise traffic, and verifies each snapshot restores.

## When to use

- After range provisioning and validation.
- Before any exercise traffic.
- After scenario validation (the baseline includes the validated scenario).

## Prerequisites

- Range fully provisioned and validated.
- Logging pipeline verified.
- Snapshot strategy published.

## Procedure

1. Quiesce the range: stop provisioning traffic, confirm steady state.
2. Capture snapshots in dependency order: storage/network, identity, endpoints, services —
   per the runbook.
3. Record metadata: exercise codename, timestamp, component versions, capture operator.
4. Verify each snapshot: integrity check plus a test restore of at least one component per
   tier.
5. Document the baseline manifest: what was captured, where it lives, how to restore.
6. Seal the baseline: mark read-only, restrict modification access.

## Expected outputs

- Baseline snapshot manifest.
- Per-component verification results.
- Sealed baseline reference.

## Pitfalls

- Capturing before validation completes — the baseline must be the validated state.
- Unverified snapshots — test-restore before sealing.
- Unsealed baselines modified later — seal it.

## References

- Backup verification literature.

## Exercise role

The pristine baseline is the range's origin point — captured carefully, verified by
restore, sealed against drift.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
