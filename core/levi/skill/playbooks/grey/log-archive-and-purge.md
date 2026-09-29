---
skill_id: grey_log_archive_and_purge
name: Exercise Log Archive and Purge
description: Archive exercise logs for analysis, then purge the pipeline for the next iteration.
risk: moderate
permissions: []
requires_confirmation: true
tags: [grey-team, resets, logs, archive]
version: 1.0.0
team: grey
---
# Exercise Log Archive and Purge

## Purpose

Exercise logs are evidence and analysis material — but the pipeline must start clean
each iteration. This procedure archives the logs immutably, verifies the archive, then
purges the live pipeline.

## When to use

- Between exercise iterations, after the analysis window.
- Before the next iteration's logging verification.

## Prerequisites

- Analysis complete or explicitly deferred with the data retained.
- Archive storage with integrity verification.
- Reset authorization.

## Procedure

1. Confirm the analysis window is closed and stakeholders agree to archival.
2. Export the exercise indices: full fidelity, with hashes per export.
3. Verify the archive: spot-restore and integrity-check before purging anything.
4. Purge the live pipeline: indices, buffers, forwarder queues — per the retention policy.
5. Verify the purge: pipeline empty, ready for the next iteration's canary verification.
6. Log the archive location, hashes, and purge completion.

## Expected outputs

- Archive manifest with hashes.
- Spot-restore verification.
- Purge-completion log.

## Pitfalls

- Purging before archive verification — the archive must be proven before the source
  dies.
- Incomplete exports — verify index completeness, not just job success.
- Retention-policy violations — follow the policy, document exceptions.

## References

- NIST SP 800-92 (log management).

## Exercise role

Logs are archived as evidence and purged as hygiene — verified in that order, always.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
