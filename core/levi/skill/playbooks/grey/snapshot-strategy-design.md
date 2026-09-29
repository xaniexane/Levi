---
skill_id: grey_snapshot_strategy_design
name: Exercise Snapshot Strategy Design
description: Design the snapshot strategy: what gets snapshotted, when, and how long it's kept.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, snapshots, strategy, design]
version: 1.0.0
team: grey
---
# Exercise Snapshot Strategy Design

## Purpose

Snapshots are the range's time machine — but only if the strategy covers the right
components at the right moments with sane retention. This design defines the snapshot
strategy before the exercise needs it.

## When to use

- During exercise planning.
- For range programs (persistent strategy across exercises).

## Prerequisites

- Range component inventory.
- Storage capacity for snapshots.
- Retention policy.

## Procedure

1. Inventory snapshot-capable components: VMs, DCs, network devices, cloud resources.
2. Define snapshot points: pristine baseline, pre-phase, pre-destructive-test, on-demand.
3. Define naming and metadata: exercise codename, timestamp, purpose, creator.
4. Define retention: how long snapshots live, when they're deleted, who approves deletion.
5. Define verification: snapshot integrity checks and periodic restore tests.
6. Publish the strategy; brief the grey team.

## Expected outputs

- Snapshot strategy document.
- Snapshot-point schedule.
- Retention and verification policy.

## Pitfalls

- No strategy — snapshots taken ad hoc, named 'final-final-2', kept forever.
- Unverified snapshots — a snapshot that doesn't restore is a hope, not a backup.
- No retention — snapshot sprawl eats the storage.

## References

- Backup and recovery literature.

## Exercise role

The snapshot strategy is the range's memory policy — designed before the exercise, or
snapshots become clutter.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
