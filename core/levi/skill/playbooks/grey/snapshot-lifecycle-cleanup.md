---
skill_id: grey_snapshot_lifecycle_cleanup
name: Snapshot Lifecycle Cleanup
description: Clean up expired snapshots per the retention policy with verification.
risk: moderate
permissions: []
requires_confirmation: true
tags: [grey-team, snapshots, lifecycle, cleanup]
version: 1.0.0
team: grey
---
# Snapshot Lifecycle Cleanup

## Purpose

Snapshots accumulate: every phase, every iteration, every 'just in case'. This cleanup
enforces the retention policy — deleting expired snapshots after verifying nothing
depends on them. MODERATE because deletion is irreversible.

## When to use

- Per the retention schedule.
- When snapshot storage approaches capacity.

## Prerequisites

- Retention policy with expiry rules.
- Snapshot manifest with creation dates and purposes.
- Deletion authorization.

## Procedure

1. List snapshots past retention: expired per the policy.
2. Verify no dependency: no planned reset, no pending analysis, no linked clones.
3. Confirm deletion authorization for the expired set.
4. Delete per the platform's safe procedure; verify deletion and storage reclamation.
5. Log every deletion: what, when, why, who authorized.
6. Report storage status post-cleanup.

## Expected outputs

- Expired-snapshot list with dependency checks.
- Deletion log with authorizations.
- Post-cleanup storage report.

## Pitfalls

- Deleting snapshots with pending analysis — check the analysis window.
- Breaking linked clones — verify dependencies first.
- Deleting without authorization — the policy plus explicit approval.

## References

- Data-lifecycle literature.

## Exercise role

Snapshot cleanup is retention policy with teeth — verified dependencies, authorized
deletions, logged everything.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
