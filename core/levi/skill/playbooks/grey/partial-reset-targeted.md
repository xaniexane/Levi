---
skill_id: grey_partial_reset_targeted
name: Targeted Partial Reset
description: Reset specific range components without a full-range reset.
risk: moderate
permissions: []
requires_confirmation: true
tags: [grey-team, resets, targeted, surgical]
version: 1.0.0
team: grey
---
# Targeted Partial Reset

## Purpose

Sometimes only one component needs resetting: a compromised server, a polluted AD OU, a
misconfigured firewall. This procedure resets surgically — the named components only —
without disturbing the rest of the running exercise.

## When to use

- Mid-exercise, when one component is unrecoverable but the exercise continues.
- To fix a broken scenario element without restarting.

## Prerequisites

- Component-level snapshots or rebuild procedures.
- White-cell approval (mid-exercise changes need control authority).
- Reset authorization with the component scope explicit.

## Procedure

1. Get white-cell approval: confirm the exercise can continue around the reset.
2. Isolate the component: stop its exercise traffic, notify affected teams.
3. Reset the component from its snapshot or rebuild procedure.
4. Verify the component: health, logging, scenario functionality.
5. Reintegrate: resume traffic, confirm the exercise timeline accounts for the gap.
6. Log the partial reset with the white-cell approval reference.

## Expected outputs

- Partial-reset log with approval reference.
- Component health verification.
- Reintegration confirmation.

## Pitfalls

- Mid-exercise resets without white-cell approval — control authority, always.
- Unannounced component outages confusing teams — notify before isolating.
- Reintegration failures — verify the component works in the live exercise, not just
  alone.

## References

- Range-operations literature.

## Exercise role

The partial reset is surgery during the operation — precise, approved, and verified
before the patient wakes.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
