---
skill_id: grey_offsite_snapshot_replication
name: Offsite Snapshot Replication
description: Replicate critical snapshots offsite for range-program resilience.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, snapshots, replication, offsite]
version: 1.0.0
team: grey
---
# Offsite Snapshot Replication

## Purpose

The range program's baselines are valuable: rebuilt scenarios, validated configurations.
This replication copies critical snapshots offsite — so a site failure doesn't erase the
program's foundation.

## When to use

- For persistent range programs.
- After major baseline updates.
- Per the replication schedule.

## Prerequisites

- Offsite storage with adequate capacity and security.
- Critical-snapshot list (baselines, gold images).
- Encryption for snapshots in transit and at rest.

## Procedure

1. Identify the critical snapshots: pristine baselines, gold images, validated scenario
   states.
2. Replicate encrypted copies offsite per the schedule.
3. Verify the replicas: integrity checks and periodic test restores.
4. Document the replica inventory with locations and verification status.
5. Define the repatriation procedure: how snapshots come back if the primary site fails.
6. Report replication status to the program lead.

## Expected outputs

- Replica inventory with verification status.
- Repatriation procedure.
- Replication status report.

## Pitfalls

- Unencrypted snapshots offsite — encrypt in transit and at rest.
- Unverified replicas — a replica that doesn't restore is a false comfort.
- No repatriation procedure — replication without a return path is half a plan.

## References

- Backup replication literature.

## Exercise role

Offsite replication protects the program's foundation — encrypted, verified, and
returnable.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
