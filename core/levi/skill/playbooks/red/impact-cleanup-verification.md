---
skill_id: red_impact_cleanup_verification
name: Impact Exercise Cleanup Verification
description: Verify complete cleanup after impact exercises to validate range hygiene.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, impact, cleanup, hygiene]
version: 1.0.0
team: red
tests_blue: cyber_conducting_post_incident_lessons_learned
---
# Impact Exercise Cleanup Verification

## Purpose

Impact exercises are destructive by design — this verification pass proves the range is
clean afterward: no canary encryption, no test backups altered, no drill artifacts left
to confuse future operations.

## When to use

- After every impact exercise, as the mandatory close-out.
- Before the range is returned to general use.

## Prerequisites

- Inventory of all impact-exercise artifacts.

## Procedure

1. Enumerate all impact-test artifacts: encrypted canary data, test backups, drill systems.
2. Verify lab systems restored to pre-exercise snapshots.
3. Confirm backup targets untouched (canary backups verified intact).
4. Check for leftover scheduled tasks, services, or accounts from the exercises.
5. Sign off the range-clean certificate with the blue team.
6. Deliver the cleanup-verification report.

## Expected outputs

- Artifact inventory with disposition.
- Snapshot-restoration verification.
- Range-clean sign-off.

## Pitfalls

- Assuming the snapshot restore worked — verify, then sign.
- Rushing close-out — cleanup verification is a phase, not an afterthought.

## References

- Exercise-hygiene best practices (internal).

## Blue-team control under test

This playbook validates their range hygiene is verified — a clean range is the
precondition for the next exercise. Paired blue-team counterpart:
`cyber_conducting_post_incident_lessons_learned`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
