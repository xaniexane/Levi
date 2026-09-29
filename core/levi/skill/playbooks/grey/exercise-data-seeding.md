---
skill_id: grey_exercise_data_seeding
name: Exercise Data Seeding
description: Seed canary data across the range: documents, credentials, and tripwires.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, canary, data]
version: 1.0.0
team: grey
---
# Exercise Data Seeding

## Purpose

Exercises need data worth stealing and tripwires worth tripping: canary documents on
shares, canary credentials in vaults, canary tokens in code. This provisioning plants
the data layer the red team hunts and the blue team defends — all fake, all tracked.

## When to use

- During range provisioning, after endpoints and shares exist.
- For data-theft and DLP exercises.
- To plant tripwires for detection validation.

## Prerequisites

- Canary-data generation tooling.
- Range file shares, mailboxes, and repos ready.
- Canary registry: every planted item recorded.

## Procedure

1. Generate canary data: documents with canary patterns, fake credentials, API tokens, PII-
   shaped fakes.
2. Plant per the scenario map: shares, endpoints, mailboxes, repos, cloud storage.
3. Plant tripwires: canary files with alerting (canary tokens that beacon when used).
4. Record every planted item in the canary registry: location, type, expected alerts.
5. Verify plantings: spot-check that canary files exist and tripwires fire.
6. Hand over the canary registry to the white cell (sealed from red and blue as the
   scenario dictates).

## Expected outputs

- Canary registry with locations and types.
- Tripwire verification results.
- Sealed registry handover.

## Pitfalls

- Unregistered canary data — every planted item tracked, no exceptions.
- Canary credentials that work on real systems — range-scoped only.
- Tripwires the blue team doesn't know are tripwires — coordinate per the scenario's
  secrecy rules.

## References

- Canary-token literature; deception literature.

## Exercise role

Canary data is the exercise's bait and tripwire — planted deliberately, registered
completely, and never real.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
